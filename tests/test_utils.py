# -*- coding: utf-8 -*-
# Copyright (c) 2025. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root for details.

"""Unit tests for logging and utility helpers."""

from unittest.mock import MagicMock, patch

from app.settings import AppSettings
from app.utils import configure_logging


def make_app_settings():
    settings = MagicMock(spec=AppSettings)
    # Simulate settings.logging with loggers dict
    settings.logging = MagicMock()
    settings.logging.loggers = {"test_logger": {"level": "INFO"}}
    return settings


@patch("app.utils.create_logging_config")
@patch("app.utils.logging.config.dictConfig")
def test_configure_logging_applies_config(mock_dictConfig, mock_create_config):
    settings = make_app_settings()
    mock_create_config.return_value = {"version": 1}
    configure_logging(settings)
    mock_create_config.assert_called_once_with(settings.logging)
    mock_dictConfig.assert_called_once_with({"version": 1})


@patch("app.utils.create_logging_config")
@patch("app.utils.logging.config.dictConfig")
def test_configure_logging_sets_logger_levels(mock_dictConfig, mock_create_config):
    settings = make_app_settings()
    mock_create_config.return_value = {"version": 1}
    with patch("app.utils.logging.getLogger") as mock_getLogger:
        mock_logger = MagicMock()
        mock_getLogger.return_value = mock_logger
        configure_logging(settings)
        mock_getLogger.assert_called_with("test_logger")
        mock_logger.setLevel.assert_called_with(20)  # logging.INFO
