"""Test init."""
from homeassistant.setup import async_setup_component

from . import INPUT_SENSOR


async def test_setup_unload(hass, mock_iotawatt, entry):
    """Test we can setup and unload an entry."""
    mock_iotawatt.getSensors.return_value["sensors"]["my_sensor_key"] = INPUT_SENSOR
    assert await async_setup_component(hass, "iotawatt", {})
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(entry.entry_id)
