"""The tests for the litejet component."""
from homeassistant.components import switch
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON

from . import async_init_integration

ENTITY_SWITCH = "switch.mock_switch_1"
ENTITY_SWITCH_NUMBER = 1
ENTITY_OTHER_SWITCH = "switch.mock_switch_2"
ENTITY_OTHER_SWITCH_NUMBER = 2


async def test_on_off(hass, mock_litejet):
    """Test turning the switch on and off."""

    await async_init_integration(hass, use_switch=True)

    assert hass.states.get(ENTITY_SWITCH).state == "off"
    assert hass.states.get(ENTITY_OTHER_SWITCH).state == "off"

    assert not switch.is_on(hass, ENTITY_SWITCH)

    await hass.services.async_call(
        switch.DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_SWITCH}, blocking=True
    )
    mock_litejet.press_switch.assert_called_with(ENTITY_SWITCH_NUMBER)

    await hass.services.async_call(
        switch.DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_SWITCH}, blocking=True
    )
    mock_litejet.release_switch.assert_called_with(ENTITY_SWITCH_NUMBER)


async def test_pressed_event(hass, mock_litejet):
    """Test handling an event from LiteJet."""

    await async_init_integration(hass, use_switch=True)

    # Switch 1
    mock_litejet.switch_pressed_callbacks[ENTITY_SWITCH_NUMBER]()
    await hass.async_block_till_done()

    assert switch.is_on(hass, ENTITY_SWITCH)
    assert not switch.is_on(hass, ENTITY_OTHER_SWITCH)
    assert hass.states.get(ENTITY_SWITCH).state == "on"
    assert hass.states.get(ENTITY_OTHER_SWITCH).state == "off"

    # Switch 2
    mock_litejet.switch_pressed_callbacks[ENTITY_OTHER_SWITCH_NUMBER]()
    await hass.async_block_till_done()

    assert switch.is_on(hass, ENTITY_OTHER_SWITCH)
    assert switch.is_on(hass, ENTITY_SWITCH)
    assert hass.states.get(ENTITY_SWITCH).state == "on"
    assert hass.states.get(ENTITY_OTHER_SWITCH).state == "on"


async def test_released_event(hass, mock_litejet):
    """Test handling an event from LiteJet."""

    await async_init_integration(hass, use_switch=True)

    # Initial state is on.
    mock_litejet.switch_pressed_callbacks[ENTITY_OTHER_SWITCH_NUMBER]()
    await hass.async_block_till_done()

    assert switch.is_on(hass, ENTITY_OTHER_SWITCH)

    # Event indicates it is off now.
    mock_litejet.switch_released_callbacks[ENTITY_OTHER_SWITCH_NUMBER]()
    await hass.async_block_till_done()

    assert not switch.is_on(hass, ENTITY_OTHER_SWITCH)
    assert not switch.is_on(hass, ENTITY_SWITCH)
    assert hass.states.get(ENTITY_SWITCH).state == "off"
    assert hass.states.get(ENTITY_OTHER_SWITCH).state == "off"
