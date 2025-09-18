"""Shared test fixtures for Fluss+ integration."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from fluss_api import FlussApiClient
import pytest

from homeassistant.components.fluss.coordinator import FlussDataUpdateCoordinator
from homeassistant.config_entries import ConfigEntry, MockConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_hass() -> MagicMock:
    """Mock Hass Environment."""
    hass = MagicMock(spec=HomeAssistant)
    hass.config_entries = MagicMock()
    hass.config_entries.async_forward_entry_setups = MagicMock()
    hass.config_entries.async_forward_entry_unload = MagicMock()
    hass.config_entries.async_unload_platforms = MagicMock()
    hass.data = {}
    return hass


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock config entry."""
    return MockConfigEntry(
        domain="fluss",
        data={CONF_API_KEY: "test_api_key"},
        unique_id="test_unique_id",
    )


@pytest.fixture
def mock_api_client() -> MagicMock:
    """Mock Fluss API client."""
    client = MagicMock(spec=FlussApiClient)
    client.async_get_devices = MagicMock(return_value={"devices": [{"deviceId": "1", "deviceName": "Test Device"}]})
    client.async_trigger_device = MagicMock()
    return client


@pytest.fixture
def mock_coordinator(
    hass: HomeAssistant, mock_config_entry: ConfigEntry, mock_api_client: MagicMock
) -> FlussDataUpdateCoordinator:
    """Mock Fluss coordinator."""
    with patch("fluss_api.FlussApiClient", return_value=mock_api_client):
        coordinator = FlussDataUpdateCoordinator(hass, mock_config_entry)
        coordinator.async_config_entry_first_refresh = MagicMock()
        return coordinator