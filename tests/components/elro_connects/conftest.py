"""Fixtures for testing the Elro Connects integration."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.elro_connects.const import (
    CONF_CONNECTOR_ID,
    CONF_UPDATE_INTERVAL,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_k1_connector():
    """Mock the Elro K1 connector."""
    with patch(
        "homeassistant.components.elro_connects.device.ElroConnectsK1.async_connect",
        AsyncMock(),
    ), patch(
        "homeassistant.components.elro_connects.device.ElroConnectsK1.async_disconnect",
        AsyncMock(),
    ), patch(
        "homeassistant.components.elro_connects.device.ElroConnectsK1.async_configure",
        AsyncMock(),
    ), patch(
        "homeassistant.components.elro_connects.device.ElroConnectsK1.async_process_command",
        AsyncMock(return_value={}),
    ) as mock_result:
        yield mock_result


@pytest.fixture
def mock_entry(hass: HomeAssistant) -> ConfigEntry:
    """Mock a Elro Connects config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_CONNECTOR_ID: "ST_deadbeef0000",
            CONF_PORT: 1025,
            CONF_UPDATE_INTERVAL: 15,
        },
    )
    entry.add_to_hass(hass)
    return entry
