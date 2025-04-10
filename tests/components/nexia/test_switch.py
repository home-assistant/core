"""The switch tests for the nexia platform."""

from datetime import timedelta

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    EVENT_HOMEASSISTANT_STOP,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import utcnow

from .util import async_init_integration

from tests.common import async_fire_time_changed


async def test_hold_switch(hass: HomeAssistant) -> None:
    """Test creation of the hold switch."""
    await async_init_integration(hass)
    assert hass.states.get("switch.nick_office_hold").state == STATE_ON


async def test_nexia_sensor_switch(hass: HomeAssistant) -> None:
    """Test NexiaRoomIQSensorSwitch."""
    await async_init_integration(hass, house_fixture="nexia/sensors_xl1050_house.json")
    sw1_id = f"{Platform.SWITCH}.center_nativezone_include_center"
    sw1 = {ATTR_ENTITY_ID: sw1_id}
    sw2_id = f"{Platform.SWITCH}.center_nativezone_include_upstairs"
    sw2 = {ATTR_ENTITY_ID: sw2_id}

    # Switch starts out on.
    assert (entity_state := hass.states.get(sw1_id)) is not None
    assert entity_state.attributes.get("request_pending") is False
    assert entity_state.state == STATE_ON

    # Turn switch off.
    await hass.services.async_call(SWITCH_DOMAIN, SERVICE_TURN_OFF, sw1, blocking=True)
    entity_state = hass.states.get(sw1_id)
    assert entity_state.attributes.get("request_pending") is True
    assert entity_state.state == STATE_OFF

    # Turn switch back on.
    await hass.services.async_call(SWITCH_DOMAIN, SERVICE_TURN_ON, sw1, blocking=True)
    assert hass.states.get(sw1_id).state == STATE_ON

    # The other switch also starts out on.
    assert (entity_state := hass.states.get(sw2_id)) is not None
    assert entity_state.state == STATE_ON

    # Turn both switches off, an invalid combination.
    await hass.services.async_call(SWITCH_DOMAIN, SERVICE_TURN_OFF, sw1, blocking=True)
    await hass.services.async_call(SWITCH_DOMAIN, SERVICE_TURN_OFF, sw2, blocking=True)
    assert hass.states.get(sw1_id).state == STATE_OFF
    assert hass.states.get(sw2_id).state == STATE_OFF

    # Wait for switches to revert to device status.
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=4))
    await hass.async_block_till_done()
    entity_state = hass.states.get(sw1_id)
    assert entity_state.attributes.get("request_pending") is False
    assert entity_state.state == STATE_ON
    assert hass.states.get(sw2_id).state == STATE_ON

    # Turn switch off.
    await hass.services.async_call(SWITCH_DOMAIN, SERVICE_TURN_OFF, sw2, blocking=True)
    entity_state = hass.states.get(sw2_id)
    assert entity_state.attributes.get("request_pending") is True
    assert entity_state.state == STATE_OFF

    # Exercise shutdown path.
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    entity_state = hass.states.get(sw2_id)
    assert entity_state.attributes.get("request_pending") is False
    assert entity_state.state == STATE_ON
