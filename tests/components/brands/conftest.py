"""Test configuration for the Brands integration."""

import pytest

from tests.typing import ClientSessionGenerator


@pytest.fixture
def hass_config_dir(hass_tmp_config_dir: str) -> str:
    """Use temporary config directory for brands tests."""
    return hass_tmp_config_dir


@pytest.fixture
def aiohttp_client(
    aiohttp_client: ClientSessionGenerator,
    socket_enabled: None,
) -> ClientSessionGenerator:
    """Return aiohttp_client and allow opening sockets."""
    return aiohttp_client
