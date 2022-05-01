"""The test for the sensibo binary sensor platform."""

from unittest.mock import patch

from homeassistant.core import HomeAssistant

from . import init_integration
from .response import DATA_FROM_API


async def test_binary_sensor(hass: HomeAssistant) -> None:
    """Test the Sensibo binary sensor."""
    entry = await init_integration(hass, entry_id="hallway_BS")
    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=DATA_FROM_API,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state1 = hass.states.get("binary_sensor.hallway_motion_sensor_alive")
    state2 = hass.states.get("binary_sensor.hallway_motion_sensor_main_sensor")
    state3 = hass.states.get("binary_sensor.hallway_motion_sensor_motion")
    state4 = hass.states.get("binary_sensor.hallway_room_occupied")
    assert state1.state == "on"
    assert state2.state == "on"
    assert state3.state == "on"
    assert state4.state == "on"
