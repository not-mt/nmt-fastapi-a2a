# -*- coding: utf-8 -*-
# Copyright (c) 2025. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root for details.

"""WidgetsMCPAgent implementation for streaming queries to MCP server."""

import logging
import traceback
from collections.abc import AsyncIterable
from typing import Any

import httpx

# NOTE: import `instructor` lazily inside the constructor to avoid
# importing heavy third-party modules at module-import time (which can
# emit pydantic deprecation warnings from dependencies). This keeps
# test runs and static imports quieter.
from jinja2 import Template
from mcp import ClientSession, Tool
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import CallToolResult, TextContent
from pydantic import BaseModel

from app.agents.middleware import OAUTH_TOKEN_CTX
from app.settings import AppSettings

logger = logging.getLogger(__name__)


class ToolCall(BaseModel):
    """
    Represents a tool call made by the WidgetsAgent.
    """

    tool_name: str
    args: dict


class WidgetsMCPAgent:
    """
    Agent to access a Sample/Widgets API MCP Server.

    Initialize the WidgetsMCPAgent with application settings.

    Args:
        settings: Application settings containing A2A configuration.

    Attributes:
        SUPPORTED_CONTENT_TYPES (list[str]): Supported content types the agent accepts
            and emits (for example, 'text' and 'text/plain').
    """

    SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]

    def __init__(self, settings: AppSettings):
        self.mcp_url = settings.a2a.agents["widgets"].mcp_url

        # Lazy-import instructor to avoid importing transitive packages that
        # may use class-based pydantic Configs at module import time.
        import instructor

        self.client = instructor.from_provider(
            settings.a2a.llm_provider.name,
            base_url=settings.a2a.llm_provider.base_url,
        )

        # openai_api_key = os.getenv("OPENAI_API_KEY")  # Or set your key directly
        # self.client = instructor.from_provider(
        #     "openai/chatgpt",
        #     api_key=openai_api_key,
        #     model="gpt-3.5-turbo"  # or "gpt-4" if you have access
        # )

        self.initialized = True
        logger.info("Widgets MCP Agent initialized successfully")

    async def _discover_mcp_tools(self, session: ClientSession) -> list[Tool]:
        """
        Discover available tools from the MCP server.
        """
        try:
            tools_result = await session.list_tools()
            available_tools = tools_result.tools

            logger.info(f"Discovered {len(available_tools)} tools from MCP server")
            for tool in available_tools:
                logger.debug(f"Available tool: {tool.name} - {tool.description}")

            return available_tools

        except Exception as exc:
            logger.error(f"Error discovering tools: {exc}")
            traceback.print_exc()
            return []

    def _select_tool(self, tools: list[Tool], question: str) -> ToolCall:
        """
        Select the best tool to invoke for the given question.

        This uses the agent's LLM client to choose a tool from the provided
        list and to produce the arguments required to call it.

        Args:
            tools: The list of available tools retrieved from the MCP server.
            question: The user's query to be routed to a tool.

        Returns:
            ToolCall: A ToolCall model describing the selected tool and its args.
        """
        model: ToolCall = self.client.chat.completions.create(
            response_model=ToolCall,
            messages=[
                {
                    "role": "system",
                    "content": """
                        You are a tool router. Given a list of tools and a user query,
                        return which tool to invoke and the arguments.

                        The implications of your choice could have significant
                        consequences. Choose wisely.

                        You can ONLY select a tool from the list that you are given.
                        Do not invent a tool name.

                        If you are unsure, return "UNKNOWN" as the tool_name.
                    """,
                },
                {
                    "role": "user",
                    "content": self._render_tools_prompt(tools, question),
                },
            ],
            temperature=0,
        )  # type: ignore
        # FIXME: type error above is nonsense about coroutines, but this is not async
        return model

    def _render_tools_prompt(self, tools: list[Tool], question: str) -> str:
        """
        Render the tools prompt using a Jinja template.
        """
        template_str = """
        You have access to the following tools:

        {% for tool in tools %}
        - {{ tool.name }}:
          description: |
            {{ tool.description | indent(12) }}
          inputSchema: {{ tool.inputSchema }}

        {% endfor %}

        This is the user query: {{ question }}
        """
        template = Template(template_str)
        rendered_text = template.render(tools=tools, question=question)
        logger.info(f"Rendered tools prompt:\n\n{rendered_text}\n")
        return rendered_text

    async def stream(self, query: str, sessionId: str) -> AsyncIterable[dict[str, Any]]:
        """
        Stream updates from the MCP agent.
        """
        if not self.initialized:
            yield {
                "is_task_complete": False,
                "require_user_input": True,
                "content": (
                    "Agent initialization failed."
                    " Please check the dependencies and logs."
                ),
            }
            return

        yield {
            "is_task_complete": False,
            "require_user_input": False,
            "content": "Processing request...",
        }
        logger.info(f"Processing query: {query[:50]}...")

        try:
            headers = {}
            if token := OAUTH_TOKEN_CTX.get():
                headers = {"Authorization": token}

            available_tools: list[Tool] = []
            call_result: CallToolResult | None = None

            # NOTE: must use streamablehttp_client for remote MCP; do NOT use SSE
            async with streamablehttp_client(
                self.mcp_url,
                headers=headers,
            ) as (
                read_stream,
                write_stream,
                get_session_id,
            ):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    available_tools = await self._discover_mcp_tools(session)
                    tool_call = self._select_tool(available_tools, query)
                    logger.info(
                        f"Selected tool: {tool_call.tool_name} with args {tool_call.args}"
                    )
                    try:
                        call_result = await session.call_tool(
                            name=tool_call.tool_name,
                            arguments=tool_call.args,
                        )
                    except Exception as exc:
                        logger.error(f"Error during MCP call: {exc!s}")

            assert isinstance(call_result, CallToolResult)
            assert isinstance(call_result.content[0], TextContent)
            text_content: TextContent = call_result.content[0]

            if call_result.isError:
                logger.error(f"Tool call failed: {call_result!s}")
                # NOTE: yield that the task is complete, and return immediately
                #   so that the client can handle the error gracefully
                yield {
                    # "is_task_complete": False,
                    # "require_user_input": True,
                    "is_task_complete": True,
                    "require_user_input": False,
                    # "content": f"Tool call failed: {call_result!s}",
                    # "content": f"Tool call failed: {call_result.json()}",
                    "content": f"Tool call failed: {text_content.text}",
                }
                return

            logger.info(f"MCP tool call response: {call_result}")

            # TODO: use instructor to format result with an explanation

            # TODO: serialize result so that an explanation can be handed back in
            #   a human-readable way AND in JSON for further processing

            yield {
                "is_task_complete": True,
                "require_user_input": False,
                "content": f"{text_content.text}",
            }

        except* httpx.ConnectError as exc:
            logger.error(f"Error in streaming agent: {traceback.format_exc()}")
            yield {
                "is_task_complete": True,
                "require_user_input": False,
                "content": f"Error connecting to MCP server: {exc.exceptions[0]!s}",
            }

        except* Exception as exc:
            logger.error(f"Error in streaming agent: {traceback.format_exc()}")
            yield {
                "is_task_complete": True,
                "require_user_input": False,
                "content": f"Error processing request: {exc.exceptions[0]!s}",
            }

    def invoke(self, query: str, sessionId: str) -> dict[str, Any]:
        """
        Synchronous invocation of the MCP agent.

        This agent only supports streaming invocation; synchronous calls are not
        implemented and will raise NotImplementedError.

        Args:
            query: The user query to invoke synchronously.
            sessionId: The session identifier.

        Raises:
            NotImplementedError: Always raised to indicate synchronous calls are unsupported.

        Returns:
            dict[str, Any]: Never returned; this method always raises NotImplementedError.
        """
        raise NotImplementedError(
            "Synchronous invocation is not supported by this agent."
            " Use the streaming endpoint (message/stream) instead."
        )
