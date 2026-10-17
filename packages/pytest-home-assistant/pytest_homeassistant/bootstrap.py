"""Pytest plugin initialization."""

import pytest

from . import _paths


@pytest.hookimpl(tryfirst=True)
def pytest_load_initial_conftests(early_config: pytest.Config) -> None:
    """Initialize the test plugin."""
    # Load fixture overrides after third-party plugins, before test collection.
    early_config.pluginmanager.import_plugin("pytest_homeassistant.plugins")
    _paths.configure(early_config)
