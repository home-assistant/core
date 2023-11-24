"""The tests for Netgear LTE binary sensor platform."""
import pytest

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import ATTR_DEVICE_CLASS, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant


@pytest.mark.usefixtures("setup_integration", "entity_registry_enabled_by_default")
async def test_binary_sensors(hass: HomeAssistant) -> None:
    """Test for successfully setting up the Netgear LTE binary sensor platform."""
    state = hass.states.get("binary_sensor.netgear_lte_mobile_connected")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.CONNECTIVITY
    state = hass.states.get("binary_sensor.netgear_lte_wire_connected")
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.CONNECTIVITY
    state = hass.states.get("binary_sensor.netgear_lte_roaming")
    assert state.state == STATE_OFF
