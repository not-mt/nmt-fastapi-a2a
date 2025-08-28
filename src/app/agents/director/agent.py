# -*- coding: utf-8 -*-
# Copyright (c) 2025. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root for details.

"""DirectorAgent implementation for agent routing and streaming responses."""

import logging
import traceback
from collections.abc import AsyncIterable
from typing import Any
from uuid import uuid4

import httpx

# NOTE: import `instructor` lazily inside the constructor to avoid
# importing heavy third-party modules at module-import time (which can
# emit pydantic deprecation warnings from dependencies). This keeps
# test runs and static imports quieter.
from a2a.client import A2ACardResolver, A2AClient
from a2a.types import (
    Message,
    MessageSendParams,
    Part,
    Role,
    SendStreamingMessageRequest,
    TextPart,
)
from pydantic import BaseModel

from app.agents.middleware import OAUTH_TOKEN_CTX
from app.settings import AppSettings

logger = logging.getLogger(__name__)


class AgentSelectionResult(BaseModel):
    """
    Result of agent selection containing agent ID and reasoning.
    """

    agent_id: str
    reasoning: str


class DirectorAgent:
    """
    Agent to direct/route to other agents based on user query.
    """

    SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]

    def __init__(self, settings: AppSettings):

        # Lazy-import `instructor` to avoid importing heavy third-party
        # libraries (and their transitive dependencies) at module import
        # time which can trigger pydantic deprecation warnings during
        # test collection or static analysis.
        import instructor

        # self.client = instructor.from_provider("openai/gpt-4o")
        # self.client = instructor.from_provider("ollama/mistral:7b")
        # self.client = instructor.from_provider("ollama/deepseek-r1:8b")
        # self.client = instructor.from_provider("ollama/qwen3:0.6b")
        # self.client = instructor.from_provider("ollama/deepseek-r1:1.5b")
        self.client = instructor.from_provider(
            settings.a2a.llm_provider.name,
            base_url=settings.a2a.llm_provider.base_url,
        )
        widgets_base_url = settings.a2a.director.agents["widgets"]

        self.httpx_clients = {}
        self.httpx_clients["widgets"] = httpx.AsyncClient(
            base_url=widgets_base_url,
        )

        self.a2a_resolvers = {}
        self.a2a_resolvers["widgets"] = A2ACardResolver(
            httpx_client=self.httpx_clients["widgets"],
            base_url=widgets_base_url,
        )

        self.a2a_clients = {}
        self.a2a_clients["widgets"] = A2AClient(
            httpx_client=self.httpx_clients["widgets"],
            url=widgets_base_url,
        )

        self.initialized = True
        logger.info("Director agent initialized successfully")

    def _select_agent(self, question: str) -> AgentSelectionResult:
        """
        Select the appropriate downstream agent for a user question.

        Uses the LLM client to choose an agent ID from the available options and
        returns the agent id along with the model's reasoning.

        Args:
            question: The user's query to route.

        Returns:
            AgentSelectionResult: An AgentSelectionResult containing the chosen agent id and reasoning.
        """
        #
        # TODO: change this to use Jinja template like in widgets agent
        #

        model: AgentSelectionResult = self.client.chat.completions.create(
            response_model=AgentSelectionResult,
            messages=[
                {
                    "role": "system",
                    "content": """
                        You are an agent router. Given a user question, return the correct
                        agent_id and explain your reasoning.

                        You have access to the following agent IDs:
                        - WidgetsAgent: for anything related to widgets, widget IDs, or zapping widget.
                        - UNKNOWN: for anything not covered by the other agents.

                        You can ONLY select an agent ID from the list above.
                        Do not invent an agent ID.
                        If you are unsure, return "UNKNOWN" as the agent_id.
                    """,
                },
                {"role": "user", "content": question},
            ],
            temperature=0,
        )  # type: ignore
        # FIXME: type error above is nonsense about coroutines, but this is not async

        return model

    async def stream(self, query: str, sessionId: str) -> AsyncIterable[dict[str, Any]]:
        """
        Stream updates from the director agent.
        """
        if not self.initialized:
            yield {
                "is_task_complete": False,
                "require_user_input": True,
                "content": "Agent initialization failed.",
            }
            return

        try:
            yield {
                "is_task_complete": False,
                "require_user_input": False,
                "content": "Processing request...",
            }
            logger.info(f"Processing query: {query[:50]}...")
            headers = {}
            if token := OAUTH_TOKEN_CTX.get():
                headers = {"Authorization": token}

            agent_choice = self._select_agent(query)

            a2a_client: A2AClient | None = None
            if agent_choice.agent_id == "WidgetsAgent":
                a2a_client = self.a2a_clients["widgets"]
            assert a2a_client is not None, f"Unknown agent_id: {agent_choice.agent_id}"

            msg = Message(
                role=Role.user,
                parts=[Part(root=TextPart(text=query))],
                message_id=uuid4().hex,
            )
            streaming_request = SendStreamingMessageRequest(
                id=str(uuid4()), params=MessageSendParams(message=msg)
            )
            content = ""
            try:
                stream_response = a2a_client.send_message_streaming(
                    streaming_request,
                    http_kwargs={"headers": headers},
                )
                async for chunk in stream_response:
                    chunk_dict = chunk.model_dump(mode="json", exclude_none=True)
                    result = chunk_dict.get("result")
                    if result and result.get("lastChunk"):
                        artifact = result.get("artifact")
                        if artifact:
                            parts = artifact.get("parts", [])
                            for part in parts:
                                if part.get("kind") == "text" and part.get("text"):
                                    content = part["text"]
                                    break
                        if not content:
                            content = str(chunk_dict)
            except Exception as e:
                logger.error(f"Error contacting agent: {traceback.format_exc()}")
                yield {
                    "is_task_complete": False,
                    "require_user_input": True,
                    "content": f"Error processing request: {e!s}",
                }

            yield {
                "is_task_complete": True,
                "require_user_input": False,
                "content": f"Agent {agent_choice.agent_id} response: {content}.",
            }

        except Exception as e:
            logger.error(f"Error in streaming agent: {traceback.format_exc()}")
            yield {
                "is_task_complete": False,
                "require_user_input": True,
                "content": f"Error processing request: {e!s}",
            }

    def invoke(self, query: str, sessionId: str) -> dict[str, Any]:
        """
        Synchronous invocation of the agent.
        """
        raise NotImplementedError(
            "Synchronous invocation is not supported by this agent."
            " Use the streaming endpoint (message/stream) instead."
        )
