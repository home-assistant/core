"""Test init."""

from unittest.mock import MagicMock

import httpx

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import INPUT_SENSOR

from tests.common import MockConfigEntry


async def test_setup_unload(
    hass: HomeAssistant, mock_iotawatt: MagicMock, entry: MockConfigEntry
) -> None:
    """Test we can setup and unload an entry."""
    mock_iotawatt.getSensors.return_value["sensors"]["my_sensor_key"] = INPUT_SENSOR
    assert await async_setup_component(hass, "iotawatt", {})
    await hass.async_block_till_done()
    assert entry.unique_id == "mock-mac"
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_setup_connection_failed(
    hass: HomeAssistant, mock_iotawatt: MagicMock, entry: MockConfigEntry
) -> None:
    """Test connection error during startup."""
    mock_iotawatt.connect.side_effect = httpx.ConnectError("")
    assert await async_setup_component(hass, "iotawatt", {})
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_auth_failed(
    hass: HomeAssistant, mock_iotawatt: MagicMock, entry: MockConfigEntry
) -> None:
    """Test auth error during startup."""
    mock_iotawatt.connect.return_value = False
    assert await async_setup_component(hass, "iotawatt", {})
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_duplicate_unique_id_fails(
    hass: HomeAssistant, mock_iotawatt: MagicMock, entry: MockConfigEntry
) -> None:
    """Test setup fails when another entry already uses the unique ID."""
    mock_iotawatt.getSensors.return_value["sensors"]["my_sensor_key"] = INPUT_SENSOR
    duplicate_entry = MockConfigEntry(domain="iotawatt", data={"host": "2.3.4.5"})
    duplicate_entry.add_to_hass(hass)

    assert await async_setup_component(hass, "iotawatt", {})
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert duplicate_entry.state is ConfigEntryState.SETUP_ERROR
