# -*- coding: utf-8 -*-
# Copyright (c) 2025. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root for details.

"""Tests for the Director app entrypoint and CLI behavior."""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

import app.director as director_module


@pytest.fixture
def mock_settings():
    with patch("app.director.get_app_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.a2a.director.host = "127.0.0.1"
        mock_settings.a2a.director.port = 8000
        mock_get_settings.return_value = mock_settings
        yield mock_settings


@pytest.fixture
def mock_configure_logging():
    with patch("app.director.configure_logging") as mock_configure:
        yield mock_configure


@pytest.fixture
def mock_uvicorn_run():
    with patch("app.director.uvicorn.run") as mock_run:
        yield mock_run


@pytest.fixture
def mock_A2AStarletteApplication():
    with patch("app.director.A2AStarletteApplication") as mock_app:
        mock_instance = MagicMock()
        mock_app.return_value = mock_instance
        mock_instance.build.return_value = MagicMock()
        yield mock_app


@pytest.fixture
def mock_DefaultRequestHandler():
    with patch("app.director.DefaultRequestHandler") as mock_handler:
        mock_instance = MagicMock()
        mock_handler.return_value = mock_instance
        yield mock_handler


@pytest.fixture
def mock_DirectorAgentExecutor():
    with patch("app.director.DirectorAgentExecutor") as mock_executor:
        mock_instance = MagicMock()
        mock_executor.return_value = mock_instance
        yield mock_executor


@pytest.fixture
def mock_InMemoryTaskStore():
    with patch("app.director.InMemoryTaskStore") as mock_store:
        mock_instance = MagicMock()
        mock_store.return_value = mock_instance
        yield mock_store


@pytest.fixture
def mock_OAuthTokenMiddleware():
    with patch("app.director.OAuthTokenMiddleware") as mock_middleware:
        yield mock_middleware


def test_get_agent_card(mock_settings):
    host = "localhost"
    port = 1234
    card = director_module.get_agent_card(host, port)
    assert card.name == "Director Agent"
    assert card.url == f"http://{host}:{port}/"
    assert card.version == "1.0.0"
    assert card.skills[0].id == "direct_user_query"
    assert (
        "Route user queries" in card.skills[0].description
        or "Route" in card.skills[0].description
    )


def test_main_invokes_uvicorn(
    mock_settings,
    mock_configure_logging,
    mock_uvicorn_run,
    mock_A2AStarletteApplication,
    mock_DefaultRequestHandler,
    mock_DirectorAgentExecutor,
    mock_InMemoryTaskStore,
    mock_OAuthTokenMiddleware,
):
    # Call the undecorated main function for testing
    runner = CliRunner()
    result = runner.invoke(
        director_module.main,
        ["--host", "127.0.0.1", "--port", "8000"],
    )
    assert result.exit_code == 0
    mock_uvicorn_run.assert_called()
    mock_A2AStarletteApplication.assert_called()
    mock_DefaultRequestHandler.assert_called()
    mock_DirectorAgentExecutor.assert_called()
    mock_InMemoryTaskStore.assert_called()
    # mock_OAuthTokenMiddleware.assert_called()
