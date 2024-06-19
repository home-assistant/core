"""Test init."""

import httpx

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import INPUT_SENSOR


async def test_setup_unload(hass: HomeAssistant, mock_iotawatt, entry) -> None:
    """Test we can setup and unload an entry."""
    mock_iotawatt.getSensors.return_value["sensors"]["my_sensor_key"] = INPUT_SENSOR
    assert await async_setup_component(hass, "iotawatt", {})
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_setup_connection_failed(
    hass: HomeAssistant, mock_iotawatt, entry
) -> None:
    """Test connection error during startup."""
    mock_iotawatt.connect.side_effect = httpx.ConnectError("")
    assert await async_setup_component(hass, "iotawatt", {})
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_auth_failed(hass: HomeAssistant, mock_iotawatt, entry) -> None:
    """Test auth error during startup."""
    mock_iotawatt.connect.return_value = False
    assert await async_setup_component(hass, "iotawatt", {})
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY
