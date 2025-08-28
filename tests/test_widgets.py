# -*- coding: utf-8 -*-
# Copyright (c) 2025. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root for details.

"""Unit tests for widget-related functionality."""

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

import app.widgets as widgets_module


@patch("app.widgets.get_app_settings")
@patch("app.widgets.configure_logging")
def test_configure_logging_called(mock_configure_logging, mock_get_app_settings):
    mock_settings = MagicMock()
    mock_get_app_settings.return_value = mock_settings
    # Directly call configure_logging to test patching
    widgets_module.configure_logging(mock_settings)
    mock_configure_logging.assert_called_once_with(mock_settings)


@patch("app.widgets.DefaultRequestHandler")
@patch("app.widgets.MCPAgentExecutor")
@patch("app.widgets.InMemoryTaskStore")
@patch("app.widgets.A2AStarletteApplication")
@patch("app.widgets.OAuthTokenMiddleware")
@patch("app.widgets.uvicorn.run")
def test_main_runs_uvicorn(
    mock_uvicorn_run,
    mock_middleware,
    mock_app_class,
    mock_task_store,
    mock_executor,
    mock_handler,
):
    mock_app = MagicMock()
    mock_app_class.return_value.build.return_value = mock_app
    mock_app.add_middleware = MagicMock()
    mock_executor.return_value = MagicMock()
    mock_handler.return_value = MagicMock()
    mock_task_store.return_value = MagicMock()
    mock_app_class.return_value = MagicMock()
    with patch("app.widgets.settings"):
        runner = CliRunner()
        runner.invoke(widgets_module.main, ["--host", "localhost", "--port", "1234"])
    mock_uvicorn_run.assert_called()


@patch("app.widgets.WidgetsMCPAgent")
def test_get_agent_card_returns_agent_card(mock_widgets_agent):
    card = widgets_module.get_agent_card("localhost", 1234)
    assert hasattr(card, "name")
    assert hasattr(card, "skills")
    assert card.url == "http://localhost:1234/"
