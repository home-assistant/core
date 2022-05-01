"""The test for the sensibo binary sensor platform."""

from homeassistant.core import HomeAssistant

from . import init_integration


async def test_binary_sensor(hass: HomeAssistant) -> None:
    """Test the Sensibo binary sensor."""
    await init_integration(hass, entry_id="hallway_BS")

    state1 = hass.states.get("binary_sensor.hallway_motion_sensor_alive")
    state2 = hass.states.get("binary_sensor.hallway_motion_sensor_main_sensor")
    state3 = hass.states.get("binary_sensor.hallway_motion_sensor_motion")
    state4 = hass.states.get("binary_sensor.hallway_room_occupied")
    assert state1.state == "on"
    assert state2.state == "on"
    assert state3.state == "on"
    assert state4.state == "on"
