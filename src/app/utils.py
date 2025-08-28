# -*- coding: utf-8 -*-
# Copyright (c) 2025. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root for details.

"""Utility functions for the agent orchestration system."""

import logging.config

from nmtfast.logging.v1.config import create_logging_config

from app.settings import AppSettings


def configure_logging(settings: AppSettings) -> None:
    """
    Configures logging based on the provided settings.
    """
    logging_config: dict = create_logging_config(settings.logging)
    logging.config.dictConfig(logging_config)

    for logger_name, logger in settings.logging.loggers.items():
        log_level: int = getattr(logging, logger["level"].upper())
        logging.getLogger(logger_name).setLevel(log_level)
