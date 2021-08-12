"""Fixtures for component testing."""
from unittest.mock import patch

import pytest


@pytest.fixture(scope="session", autouse=True)
def patch_zeroconf_multiple_catcher():
    """Patch zeroconf wrapper that detects if multiple instances are used."""
    with patch(
        "homeassistant.components.zeroconf.install_multiple_zeroconf_catcher",
        side_effect=lambda zc: None,
    ):
        yield


@pytest.fixture(autouse=True)
def prevent_io():
    """Fixture to prevent certain I/O from happening."""
    with patch(
        "homeassistant.components.http.ban.async_load_ip_bans_config",
        return_value=[],
    ):
        yield
