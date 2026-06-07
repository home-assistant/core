"""Fixtures for UniFi AP Direct integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.unifi_direct.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME

from tests.common import MockConfigEntry

MOCK_HOST = "192.168.1.2"
MOCK_USERNAME = "admin"
MOCK_PASSWORD = "password"
MOCK_PORT = 22

MOCK_CONFIG = {
    CONF_HOST: MOCK_HOST,
    CONF_USERNAME: MOCK_USERNAME,
    CONF_PASSWORD: MOCK_PASSWORD,
    CONF_PORT: MOCK_PORT,
}

MOCK_DEVICE_DATA = {
    "AA:BB:CC:DD:EE:FF": {"ip": "192.168.1.100", "hostname": "my-phone"},
    "11:22:33:44:55:66": {"ip": "192.168.1.101", "hostname": "my-laptop"},
}


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.unifi_direct.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, title=f"UniFi AP ({MOCK_HOST})"
    )


@pytest.fixture
def mock_unifiap() -> Generator[MagicMock]:
    """Mock UniFiAP to return known clients."""
    with patch("homeassistant.components.unifi_direct.coordinator.UniFiAP") as mock:
        ap_instance = MagicMock()
        ap_instance.get_clients.return_value = MOCK_DEVICE_DATA
        mock.return_value = ap_instance
        yield mock


@pytest.fixture
def mock_unifiap_config_flow() -> Generator[MagicMock]:
    """Mock UniFiAP for config flow."""
    with patch("homeassistant.components.unifi_direct.config_flow.UniFiAP") as mock:
        ap_instance = MagicMock()
        ap_instance.get_clients.return_value = MOCK_DEVICE_DATA
        mock.return_value = ap_instance
        yield mock
