"""Test the Envisalink binary sensors."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.envisalink.const import DOMAIN
from homeassistant.const import ATTR_DEVICE_CLASS, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


async def test_binary_sensor_state(
    hass: HomeAssistant, mock_config_entry, init_integration
) -> None:
    """Test the createion and values of the Envisalink binary sensors."""
    controller = hass.data[DOMAIN][mock_config_entry.entry_id]
    controller.async_login_success_callback()
    await hass.async_block_till_done()

    er.async_get(hass)

    state = hass.states.get("binary_sensor.test_alarm_name_zone_1")
    assert state
    assert state.state == STATE_OFF
    assert state.attributes.get("zone") == 1
    assert state.attributes.get("last_fault") is None  # TODO
    assert state.attributes.get(ATTR_DEVICE_CLASS) == BinarySensorDeviceClass.OPENING


async def test_binary_sensor_update(
    hass: HomeAssistant, mock_config_entry, init_integration
) -> None:
    """Test updating a zone's state."""
    controller = hass.data[DOMAIN][mock_config_entry.entry_id]
    controller.async_login_success_callback()
    await hass.async_block_till_done()

    er.async_get(hass)

    zones = [1, 3, 7]
    for zone in zones:
        controller.controller.alarm_state["zone"][zone]["status"]["open"] = True
    controller.async_zones_updated_callback(zones)
    await hass.async_block_till_done()

    for zone in zones:
        state = hass.states.get(f"binary_sensor.test_alarm_name_zone_{zone}")
        assert state
        assert state.state == STATE_ON
