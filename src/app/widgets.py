# -*- coding: utf-8 -*-
# Copyright (c) 2025. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root for details.

"""Entrypoint for running the WidgetsMCPAgent A2A server."""

import logging

import click
import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill

from app.agents.middleware import OAuthTokenMiddleware
from app.agents.widgets.agent import WidgetsMCPAgent
from app.agents.widgets.agent_executor import MCPAgentExecutor
from app.settings import get_app_settings
from app.utils import configure_logging

settings = get_app_settings()

configure_logging(settings)
logger = logging.getLogger(__name__)


@click.command()
@click.option("--host", "host", default=settings.a2a.agents["widgets"].host)
@click.option("--port", "port", default=settings.a2a.agents["widgets"].port)
def main(host: str, port: int) -> None:
    """
    Starts the MCP Agent server.

    Args:
        host: Host address to bind the server to.
        port: Port number to bind the server to.

    Returns:
        None: This function does not return a value.
    """
    request_handler = DefaultRequestHandler(
        agent_executor=MCPAgentExecutor(settings),
        task_store=InMemoryTaskStore(),
    )
    server = A2AStarletteApplication(
        agent_card=get_agent_card(host, port),
        http_handler=request_handler,
    )
    app = server.build()
    app.add_middleware(OAuthTokenMiddleware)

    uvicorn.run(app, host=host, port=port)


def get_agent_card(host: str, port: int) -> AgentCard:
    """
    Returns the Agent Card for the MCP Agent.

    Args:
        host: Host used to build the agent URL.
        port: Port used to build the agent URL.

    Returns:
        AgentCard: An AgentCard describing the Widgets MCP Agent.
    """
    skill = AgentSkill(
        id="widgets_api_access",
        name="Widgets API Access",
        description="Interact with the Widgets MCP Agent to discover and use available tools via API.",
        tags=["widgets", "tools", "api", "automation"],
        examples=[
            "List all available tools from the Widgets agent.",
            "Invoke a tool to process data using the Widgets API.",
        ],
    )
    card = AgentCard(
        name="Widgets MCP Agent",
        description=(
            "Agent that provides access to the Widgets API and its available tools."
            " Use this agent to discover, invoke, and automate tasks using the Widgets MCP server."
        ),
        url=f"http://{host}:{port}/",
        version="1.0.0",
        default_input_modes=WidgetsMCPAgent.SUPPORTED_CONTENT_TYPES,
        default_output_modes=WidgetsMCPAgent.SUPPORTED_CONTENT_TYPES,
        capabilities=AgentCapabilities(streaming=True),
        skills=[skill],
    )
    return card


if __name__ == "__main__":
    main()  # pragma: no cover
