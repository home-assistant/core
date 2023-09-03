"""Test the Honeywell Lyric binary sensor platform."""

from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant

from . import init_integration


async def test_room_accessories_motion_binary_sensors(hass: HomeAssistant) -> None:
    """Binary motion sensors should be created for each room accessory in data."""

    await init_integration(hass, Platform.BINARY_SENSOR)

    state = hass.states.get("binary_sensor.family_room_overall_motion")
    assert state is not None
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.hallway_overall_motion")
    assert state is not None
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.library_overall_motion")
    assert state is not None
    assert state.state == STATE_ON

    state = hass.states.get("binary_sensor.living_room_overall_motion")
    assert state is not None
    assert state.state == STATE_OFF

    state = hass.states.get("binary_sensor.master_bedroom_overall_motion")
    assert state is not None
    assert state.state == STATE_ON

    state = hass.states.get("binary_sensor.office_overall_motion")
    assert state is not None
    assert state.state == STATE_ON
