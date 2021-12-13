"""Test init."""
import httpx

from homeassistant.config_entries import ConfigEntryState
from homeassistant.setup import async_setup_component

from . import INPUT_SENSOR


async def test_setup_unload(hass, mock_iotawatt, entry):
    """Test we can setup and unload an entry."""
    mock_iotawatt.getSensors.return_value["sensors"]["my_sensor_key"] = INPUT_SENSOR
    assert await async_setup_component(hass, "iotawatt", {})
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_setup_connection_failed(hass, mock_iotawatt, entry):
    """Test connection error during startup."""
    mock_iotawatt.connect.side_effect = httpx.ConnectError("")
    assert await async_setup_component(hass, "iotawatt", {})
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.SETUP_RETRY


async def test_setup_auth_failed(hass, mock_iotawatt, entry):
    """Test auth error during startup."""
    mock_iotawatt.connect.return_value = False
    assert await async_setup_component(hass, "iotawatt", {})
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.SETUP_RETRY
