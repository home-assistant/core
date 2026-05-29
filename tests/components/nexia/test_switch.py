"""Tests for the nexia switch platform."""

from freezegun.api import FrozenDateTimeFactory
from nexia.home import NexiaHome

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

from .conftest import setup_integration

from tests.common import async_fire_time_changed


async def test_hold_switch(hass: HomeAssistant, mock_nexia_home: NexiaHome) -> None:
    """Test creation of the hold switch."""

    await setup_integration(hass, mock_nexia_home)

    entity_state = hass.states.get("switch.nick_office_nick_office_hold")
    assert entity_state is not None
    assert entity_state.state == STATE_ON


async def test_nexia_sensor_switch(
    hass: HomeAssistant, mock_nexia_home: NexiaHome, freezer: FrozenDateTimeFactory
) -> None:
    """Test NexiaRoomIQSensorSwitch."""

    await setup_integration(hass, mock_nexia_home)

    sw1_id = f"{Platform.SWITCH}.center_nativezone_center_nativezone_include_center"
    sw1 = {ATTR_ENTITY_ID: sw1_id}
    sw2_id = f"{Platform.SWITCH}.center_nativezone_center_nativezone_include_upstairs"
    sw2 = {ATTR_ENTITY_ID: sw2_id}

    # Switch starts out on
    assert (entity_state := hass.states.get(sw1_id)) is not None
    assert entity_state.state == STATE_ON

    # Turn switch off
    await hass.services.async_call(SWITCH_DOMAIN, SERVICE_TURN_OFF, sw1, blocking=True)
    assert hass.states.get(sw1_id).state == STATE_OFF

    # Turn switch back on
    await hass.services.async_call(SWITCH_DOMAIN, SERVICE_TURN_ON, sw1, blocking=True)
    assert hass.states.get(sw1_id).state == STATE_ON

    # The other switch also starts out on
    assert (entity_state := hass.states.get(sw2_id)) is not None
    assert entity_state.state == STATE_ON

    # Turn sw2 off as well — both off is an invalid combination
    await hass.services.async_call(SWITCH_DOMAIN, SERVICE_TURN_OFF, sw1, blocking=True)
    await hass.services.async_call(SWITCH_DOMAIN, SERVICE_TURN_OFF, sw2, blocking=True)
    assert hass.states.get(sw1_id).state == STATE_OFF
    assert hass.states.get(sw2_id).state == STATE_OFF

    # Wait past the harmonizer delay so it reverts to device state
    freezer.tick(6)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # After revert both should be back ON (device state from get_active_sensor_ids)
    assert hass.states.get(sw1_id).state == STATE_ON
    assert hass.states.get(sw2_id).state == STATE_ON

    # Turn sw2 off
    await hass.services.async_call(SWITCH_DOMAIN, SERVICE_TURN_OFF, sw2, blocking=True)
    assert hass.states.get(sw2_id).state == STATE_OFF

    # Firing HA stop should trigger the harmonizer shutdown, reverting state
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    assert hass.states.get(sw2_id).state == STATE_ON
