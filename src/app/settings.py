# -*- coding: utf-8 -*-
# Copyright (c) 2025. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root for details.

"""Application settings and defaults, defined with pydantic-settings."""

import logging
from typing import Optional

from nmtfast.settings.v1.config_files import get_config_files, load_config
from nmtfast.settings.v1.schemas import (
    AuthSettings,
    CacheSettings,
    IncomingAuthSettings,
    LoggingSettings,
    OutgoingAuthSettings,
    TaskSettings,
)
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


# class CustomDiscoverySettings(ServiceDiscoverySettings):
#     """
#     Application-specific configuration for service discovery.
#
#     This is a subclass of ServiceDiscoverySettings, and adds a "custom" field which
#     serves as an example of how to integrate custom service/security settings while
#     still using models from the nmtfast library.
#
#     Attributes:
#         custom: An example of custom fields that can be modeled by individual
#             applications / microservices.
#     """
#
#     custom: dict[str, dict] = {}


class DirectorSettings(BaseModel):
    """
    Settings for the Director Agent.

    Attributes:
        host: Host address for the Director Agent.
        port: Port for the Director Agent.
        agents: Maps agent names to their URLs.
    """

    host: str
    port: int
    agents: dict[str, str] = {}  # Maps agent names to their URLs


class AgentSettings(BaseModel):
    """
    Generic settings for an agent service.

    Attributes:
        host: Host address for the agent service.
        port: Port for the agent service.
        mcp_url: Base URL for the agent's MCP Service.
    """

    host: str
    port: int
    mcp_url: str


class LLMProviderSettings(BaseModel):
    """
    Settings for the LLM provider.

    Attributes:
        name: Name of the LLM provider (e.g., "ollama/deepseek-r1:8b").
        base_url: Base URL for the LLM provider API (optional).
    """

    name: str
    base_url: Optional[str] = None  # optional base URL for the LLM provider
    # TODO: authentication here?


class Agent2AgentSettings(BaseModel):
    """
    Settings for A2A client configuration.

    Attributes:
        director_url: URL for the Director Agent.
        director: Configuration for the Director Agent.
        agents: Dictionary of A2A agents (e.g., widgets, ...).
        llm_provider: LLM provider configuration.
    """

    director_url: str
    director: DirectorSettings
    agents: dict[str, AgentSettings] = {}
    llm_provider: LLMProviderSettings


class AppSettings(BaseSettings):
    """
    Application settings model.

    Attributes:
        version (int): Version of the settings schema.
        app_name (str): Name of the FastAPI application.
        auth (AuthSettings): Authentication settings.
        a2a (Agent2AgentSettings): Agent-to-agent configuration.
        logging (LoggingSettings): Logging configuration.
        tasks (TaskSettings): Task queue settings.
        cache (CacheSettings): Cache settings.
        model_config (SettingsConfigDict): pydantic settings model configuration (extra handling).
    """

    version: int = 1
    app_name: str = "My FastAPI App"
    auth: AuthSettings = AuthSettings(
        swagger_token_url="https://some.domain.tld/token",
        id_providers={},
        incoming=IncomingAuthSettings(
            clients={},
            api_keys={},
        ),
        outgoing=OutgoingAuthSettings(
            clients={},
            headers={},
        ),
    )
    # discovery: CustomDiscoverySettings = CustomDiscoverySettings(
    #     mode="manual",
    #     services={},
    #     custom={},
    # )
    a2a: Agent2AgentSettings = Agent2AgentSettings(
        director_url="http://localhost:10010",
        director=DirectorSettings(
            host="localhost",
            port=10010,
            agents={"widgets": "http://localhost:10020"},
        ),
        agents={
            "widgets": AgentSettings(
                host="localhost", port=10020, mcp_url="http://localhost:8001/mcp/"
            )
        },
        llm_provider=LLMProviderSettings(
            name="ollama/deepseek-r1:8b",
            base_url="http://127.0.0.1:11434/v1",
        ),
    )
    logging: LoggingSettings = LoggingSettings()
    tasks: TaskSettings = TaskSettings(
        name="FIXME",
        backend="sqlite",
        url="redis://:FIXME_password@FIXME_host:6379/FIXME_db_number",
        sqlite_filename="./huey.sqlite",
    )
    cache: CacheSettings = CacheSettings(
        name="nmt-fastapi-a2a",
        backend="huey",
        ttl=3600 * 4,
    )
    model_config = SettingsConfigDict(extra="ignore")


def get_app_settings() -> AppSettings:
    """
    Dependency function to provide settings.

    Returns:
        AppSettings: The application settings.
    """
    return _settings


_config_data: dict = load_config(get_config_files())
_settings: AppSettings = AppSettings(**_config_data)
