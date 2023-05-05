"""The tests for Netgear LTE binary sensor platform."""
from unittest.mock import AsyncMock

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import ATTR_DEVICE_CLASS, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from .conftest import ComponentSetup


async def test_binary_sensors(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    entity_registry_enabled_by_default: AsyncMock,
    connection,
):
    """Test for successfully setting up the Netgear LTE binary sensor platform."""
    await setup_integration()

    state = hass.states.get("binary_sensor.netgear_lte_mobile_connected")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.CONNECTIVITY
    state = hass.states.get("binary_sensor.netgear_lte_wire_connected")
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.CONNECTIVITY
    state = hass.states.get("binary_sensor.netgear_lte_roaming")
    assert state.state == STATE_OFF
