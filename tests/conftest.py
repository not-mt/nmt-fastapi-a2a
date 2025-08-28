# -*- coding: utf-8 -*-
# Copyright (c) 2025. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root for details.

"""pytest fixtures for unit / integration tests."""

import importlib
import importlib.util
import logging
import pathlib

import pytest

from app.settings import AppSettings, LoggingSettings

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


@pytest.fixture
def test_app_settings_with_loggers() -> AppSettings:
    """
    Fixture to provide an AppSettings instance with custom loggers.
    """
    logging_settings = LoggingSettings(
        level="DEBUG",
        loggers={
            "test_logger_1": {"level": "DEBUG"},
            "test_logger_2": {"level": "WARNING"},
        },
    )
    return AppSettings(logging=logging_settings)


@pytest.fixture(scope="session", autouse=True)
def discover_all_app_modules() -> None:
    """
    Fixture that discovers all implicit namespace packages in app.

    It is necessary to load all packages in order to detect missing code coverage.
    """
    package = "app"
    spec = importlib.util.find_spec(package)

    if spec is None or not spec.submodule_search_locations:
        raise ImportError(f"Could not find package: {package}")

    package_path = pathlib.Path(next(iter(spec.submodule_search_locations)))

    def discover_modules(path, parent):
        """
        Recursive inner function to discover all app modules.
        """
        for entry in path.rglob("*.py"):  # recursively find all .py files

            if entry.stem == "__init__":
                # NOTE: skip __init__.py files, but we are using implicit
                #   namespace packages so they should not be found
                continue

            # convert file path to module import path
            relative_path = entry.relative_to(path)
            module_name = (
                f"{parent}.{relative_path.with_suffix('').as_posix().replace('/', '.')}"
            )
            try:
                importlib.import_module(module_name)
                logger.info(f"Loaded module: {module_name}")
            except ImportError as exc:
                logger.error(f"Failed to load module: {module_name}, Error: {exc}")

    discover_modules(package_path, package)
    logger.info("Finished loading app modules.")
