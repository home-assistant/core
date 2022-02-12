"""Tests for switch platform."""

from pywizlight import PilotParser

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import FAKE_MAC, FAKE_SOCKET, async_setup_integration


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

    switch.status = False
    switch.state = PilotParser({"mac": FAKE_MAC, "state": False})
    switch.push_callback(switch.state)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_OFF

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    switch.turn_on.assert_called_once()

    switch.status = True
    switch.state = PilotParser({"mac": FAKE_MAC, "state": True})
    switch.push_callback(switch.state)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_ON
