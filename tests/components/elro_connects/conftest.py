"""Fixtures for testing the Elro Connects integration."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.elro_connects.const import CONF_CONNECTOR_ID, DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_k1_connector() -> dict[AsyncMock]:
    """Mock the Elro K1 connector class."""
    with patch(
        "homeassistant.components.elro_connects.device.ElroConnectsK1.async_connect",
        AsyncMock(),
    ) as mock_connect, patch(
        "homeassistant.components.elro_connects.device.ElroConnectsK1.async_disconnect",
        AsyncMock(),
    ) as mock_disconnect, patch(
        "homeassistant.components.elro_connects.device.ElroConnectsK1.async_configure",
        AsyncMock(),
    ) as mock_configure, patch(
        "homeassistant.components.elro_connects.device.ElroConnectsK1.async_process_command",
        AsyncMock(return_value={}),
    ) as mock_result:
        yield {
            "connect": mock_connect,
            "disconnect": mock_disconnect,
            "configure": mock_configure,
            "result": mock_result,
        }


@pytest.fixture
def mock_entry(hass: HomeAssistant) -> ConfigEntry:
    """Mock a Elro Connects config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_CONNECTOR_ID: "ST_deadbeef0000",
            CONF_PORT: 1025,
        },
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_k1_api(hass: HomeAssistant) -> dict[AsyncMock]:
    """Mock the Elro K1 API."""
    with patch("elro.api.K1.async_connect", AsyncMock(),) as mock_connect, patch(
        "elro.api.K1.async_disconnect",
        AsyncMock(),
    ) as mock_disconnect, patch(
        "elro.api.K1.async_configure",
        AsyncMock(),
    ) as mock_configure, patch(
        "elro.api.K1.async_process_command",
        AsyncMock(return_value={}),
    ) as mock_result:
        yield {
            "connect": mock_connect,
            "disconnect": mock_disconnect,
            "configure": mock_configure,
            "result": mock_result,
        }
