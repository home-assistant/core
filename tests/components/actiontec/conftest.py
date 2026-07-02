"""Common fixtures for the Actiontec integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.actiontec.const import DOMAIN
from homeassistant.components.actiontec.model import Device
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry

MOCK_HOST = "192.168.1.1"
MOCK_USERNAME = "admin"
MOCK_PASSWORD = "password"

MOCK_CONFIG = {
    CONF_HOST: MOCK_HOST,
    CONF_USERNAME: MOCK_USERNAME,
    CONF_PASSWORD: MOCK_PASSWORD,
}

MOCK_DEVICES = [
    Device("192.168.1.10", "AA:BB:CC:DD:EE:FF", 300),
    Device("192.168.1.11", "11:22:33:44:55:66", 300),
]


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.actiontec.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, title=MOCK_HOST)


@pytest.fixture
def mock_get_actiontec_data() -> Generator[MagicMock]:
    """Mock Actiontec data fetching."""
    mock_get_data = MagicMock(return_value=MOCK_DEVICES)
    with (
        patch(
            "homeassistant.components.actiontec.coordinator.get_actiontec_data",
            new=mock_get_data,
        ),
        patch(
            "homeassistant.components.actiontec.config_flow.get_actiontec_data",
            new=mock_get_data,
        ),
    ):
        yield mock_get_data
