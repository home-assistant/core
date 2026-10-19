"""Load Home Assistant's fixtures after third-party pytest plugins."""

import pytest

from . import _paths


@pytest.hookimpl(tryfirst=True)
def pytest_load_initial_conftests(early_config: pytest.Config) -> None:
    """Register fixture overrides before importing the consuming test suite."""
    early_config.pluginmanager.import_plugin("pytest_homeassistant.plugins")
    early_config.pluginmanager.import_plugin(
        "pytest_homeassistant.components.hassio.fixtures"
    )
    _paths.configure(early_config)
