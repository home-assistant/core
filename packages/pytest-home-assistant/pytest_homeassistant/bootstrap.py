"""Pytest plugin registration."""

import pytest

from . import _paths


def pytest_load_initial_conftests(early_config: pytest.Config) -> None:
    """Register fixture overrides before importing the consuming test suite."""
    early_config.pluginmanager.import_plugin("pytest_homeassistant.plugins")
    _paths.configure(early_config)
