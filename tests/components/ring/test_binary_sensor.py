"""The tests for the Ring binary sensor platform."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .common import setup_platform


async def test_binary_sensor(hass: HomeAssistant, mock_ring_client) -> None:
    """Test the Ring binary sensors."""
    await setup_platform(hass, Platform.BINARY_SENSOR)

    motion_state = hass.states.get("binary_sensor.front_door_motion")
    assert motion_state is not None
    assert motion_state.state == "on"
    assert motion_state.attributes["device_class"] == "motion"

    front_ding_state = hass.states.get("binary_sensor.front_door_ding")
    assert front_ding_state is not None
    assert front_ding_state.state == "off"

    ingress_ding_state = hass.states.get("binary_sensor.ingress_ding")
    assert ingress_ding_state is not None
    assert ingress_ding_state.state == "off"
