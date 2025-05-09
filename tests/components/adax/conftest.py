"""Fixtures for Adax testing."""

from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.adax.const import (
    ACCOUNT_ID,
    CLOUD,
    CONNECTION_TYPE,
    DOMAIN,
    LOCAL,
)
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_UNIQUE_ID,
)

from tests.common import AsyncMock, MockConfigEntry

CLOUD_CONFIG = {
    ACCOUNT_ID: 12345,
    CONF_PASSWORD: "pswd",
    CONNECTION_TYPE: CLOUD,
}

LOCAL_CONFIG = {
    CONF_IP_ADDRESS: "192.168.1.12",
    CONF_TOKEN: "TOKEN-123",
    CONF_UNIQUE_ID: "11:22:33:44:55:66",
    CONNECTION_TYPE: LOCAL,
}


CLOUD_DEVICE_DATA: dict[str, Any] = [
    {
        "id": "1",
        "homeId": "1",
        "name": "Room 1",
        "temperature": 15,
        "targetTemperature": 20,
        "heatingEnabled": True,
    }
]

LOCAL_DEVICE_DATA: dict[str, Any] = {
    "current_temperature": 15,
    "target_temperature": 20,
}


@pytest.fixture
def mock_cloud_config_entry(request: pytest.FixtureRequest) -> MockConfigEntry:
    """Mock a "CLOUD" config entry."""
    return MockConfigEntry(domain=DOMAIN, data=CLOUD_CONFIG)


@pytest.fixture
def mock_local_config_entry(request: pytest.FixtureRequest) -> MockConfigEntry:
    """Mock a "LOCAL" config entry."""
    return MockConfigEntry(domain=DOMAIN, data=LOCAL_CONFIG)


@pytest.fixture
def mock_adax_cloud():
    """Mock climate data."""
    with patch("homeassistant.components.adax.coordinator.Adax") as mock_adax:
        mock_adax_class = mock_adax.return_value

        mock_adax_class.get_rooms = AsyncMock()
        mock_adax_class.get_rooms.return_value = CLOUD_DEVICE_DATA

        mock_adax_class.update = AsyncMock()
        mock_adax_class.update.return_value = None
        yield mock_adax_class


@pytest.fixture
def mock_adax_local():
    """Mock climate data."""
    with patch("homeassistant.components.adax.coordinator.AdaxLocal") as mock_adax:
        mock_adax_class = mock_adax.return_value

        mock_adax_class.get_status = AsyncMock()
        mock_adax_class.get_status.return_value = LOCAL_DEVICE_DATA
        yield mock_adax_class
