"""The test for the sensibo binary sensor platform."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def test_binary_sensor(hass: HomeAssistant, load_int: ConfigEntry) -> None:
    """Test the Sensibo binary sensor."""

    state1 = hass.states.get("binary_sensor.hallway_motion_sensor_alive")
    state2 = hass.states.get("binary_sensor.hallway_motion_sensor_main_sensor")
    state3 = hass.states.get("binary_sensor.hallway_motion_sensor_motion")
    state4 = hass.states.get("binary_sensor.hallway_room_occupied")
    assert state1.state == "on"
    assert state2.state == "on"
    assert state3.state == "on"
    assert state4.state == "on"
