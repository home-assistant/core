"""Binary sensor tests for the Skybell integration."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import ATTR_DEVICE_CLASS, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from .conftest import async_init_integration


async def test_binary_sensors(hass: HomeAssistant, connection) -> None:
    """Test we get sensor data."""
    await async_init_integration(hass)

    state = hass.states.get("binary_sensor.front_door_button")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_DEVICE_CLASS) == BinarySensorDeviceClass.OCCUPANCY
    state = hass.states.get("binary_sensor.front_door_motion")
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_DEVICE_CLASS) == BinarySensorDeviceClass.MOTION
