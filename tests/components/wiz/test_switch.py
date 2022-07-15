"""Tests for switch platform."""

import datetime

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import utcnow

from . import FAKE_MAC, FAKE_SOCKET, async_push_update, async_setup_integration

from tests.common import async_fire_time_changed


async def test_switch_operation(hass: HomeAssistant) -> None:
    """Test switch operation."""
    switch, _ = await async_setup_integration(hass, bulb_type=FAKE_SOCKET)
    entity_id = "switch.mock_title"
    entity_registry = er.async_get(hass)
    assert entity_registry.async_get(entity_id).unique_id == FAKE_MAC
    assert hass.states.get(entity_id).state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    switch.turn_off.assert_called_once()

    await async_push_update(hass, switch, {"mac": FAKE_MAC, "state": False})
    assert hass.states.get(entity_id).state == STATE_OFF

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    switch.turn_on.assert_called_once()

    await async_push_update(hass, switch, {"mac": FAKE_MAC, "state": True})
    assert hass.states.get(entity_id).state == STATE_ON


async def test_update_fails(hass: HomeAssistant) -> None:
    """Test switch update fails when push updates are not working."""
    switch, _ = await async_setup_integration(hass, bulb_type=FAKE_SOCKET)
    entity_id = "switch.mock_title"
    entity_registry = er.async_get(hass)
    assert entity_registry.async_get(entity_id).unique_id == FAKE_MAC
    assert hass.states.get(entity_id).state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    switch.turn_off.assert_called_once()

    switch.updateState.side_effect = OSError

    async_fire_time_changed(hass, utcnow() + datetime.timedelta(seconds=15))
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
