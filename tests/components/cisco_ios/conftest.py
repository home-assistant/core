"""Fixtures for Cisco IOS integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.cisco_ios.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME

from tests.common import MockConfigEntry

MOCK_HOST = "192.168.1.1"
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
    "00:1D:EC:02:07:AB": "192.168.1.100",
    "00:27:D3:2D:45:67": "192.168.1.101",
}


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.cisco_ios.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, title=f"Cisco IOS ({MOCK_HOST})"
    )


@pytest.fixture
def mock_scanner() -> Generator[MagicMock]:
    """Mock CiscoIOSArpScanner to return known devices."""
    with (
        patch(
            "homeassistant.components.cisco_ios.coordinator.CiscoIOSArpScanner"
        ) as mock,
        patch(
            "homeassistant.components.cisco_ios.config_flow.CiscoIOSArpScanner",
            new=mock,
        ),
    ):
        scanner_instance = MagicMock()
        scanner_instance.get_devices.return_value = MOCK_DEVICE_DATA
        mock.return_value = scanner_instance
        yield mock
