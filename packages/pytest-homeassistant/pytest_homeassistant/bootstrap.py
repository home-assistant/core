"""Pytest plugin registration."""

import warnings

import pytest

from . import _paths

# Known warnings raised while importing Home Assistant. The import happens at
# plugin load, where a command-line -W error overrides the consuming project's
# filterwarnings, so filter them here. Mirrors core's pyproject.toml.
_IMPORT_WARNING_FILTERS = (
    # Overwrite web.Application to pass a custom default argument to _make_request
    (
        r"Inheritance class HomeAssistantApplication from web.Application is discouraged",
        r"homeassistant\.components\.http\.server",
    ),
    # https://github.com/litl/backoff/pull/220 - v2.2.1 - 2022-10-05 (archived)
    (
        r"'asyncio.iscoroutinefunction' is deprecated and slated for removal in Python 3.16",
        r"backoff\._(decorator|async)",
    ),
)


def pytest_load_initial_conftests(early_config: pytest.Config) -> None:
    """Register fixture overrides before importing the consuming test suite."""
    with warnings.catch_warnings():
        for message, module in _IMPORT_WARNING_FILTERS:
            warnings.filterwarnings("ignore", message, DeprecationWarning, module)
        early_config.pluginmanager.import_plugin("pytest_homeassistant.plugins")
    _paths.configure(early_config)
