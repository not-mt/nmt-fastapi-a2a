# -*- coding: utf-8 -*-
# Copyright (c) 2025. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root for details.

"""Entrypoint for running the DirectorAgent A2A server."""

import logging

import click
import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill

from app.agents.director.agent import DirectorAgent
from app.agents.director.agent_executor import DirectorAgentExecutor
from app.agents.middleware import OAuthTokenMiddleware
from app.settings import get_app_settings
from app.utils import configure_logging

settings = get_app_settings()

configure_logging(settings)
logger = logging.getLogger(__name__)


@click.command()
@click.option("--host", "host", default=settings.a2a.director.host)
@click.option("--port", "port", default=settings.a2a.director.port)
def main(host: str, port: int) -> None:
    """
    Starts the Director uvicorn server.

    Args:
        host: Host address to bind the server to.
        port: Port number to bind the server to.

    Returns:
        None: This function does not return a value.
    """
    request_handler = DefaultRequestHandler(
        agent_executor=DirectorAgentExecutor(settings),
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
    Returns the Agent Card for the Director agent.

    Args:
        host: Host used to build the agent URL.
        port: Port used to build the agent URL.

    Returns:
        AgentCard: The agent card describing the Director agent.
    """
    skill = AgentSkill(
        id="direct_user_query",
        name="Direct User Query",
        description="Route user queries to the appropriate agent.",
        tags=["query", "routing", "agent"],
        examples=[
            "Route this query to the appropriate agent: What is the force of widget ID 1?",
            "Route this query to the appropriate agent: Can you zap widget ID 1 for 30 seconds?",
        ],
    )
    card = AgentCard(
        name="Director Agent",
        description=("AI agent that can route user queries to the appropriate agent."),
        url=f"http://{host}:{port}/",
        version="1.0.0",
        default_input_modes=DirectorAgent.SUPPORTED_CONTENT_TYPES,
        default_output_modes=DirectorAgent.SUPPORTED_CONTENT_TYPES,
        capabilities=AgentCapabilities(streaming=True),
        skills=[skill],
    )
    return card


if __name__ == "__main__":
    main()  # pragma: no cover
