"""Test Lutron switch platform."""

from unittest.mock import MagicMock

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_switch_setup(
    hass: HomeAssistant, mock_lutron: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test switch setup."""
    mock_config_entry.add_to_hass(hass)

    # Mock levels
    switch = mock_lutron.areas[0].outputs[1]
    switch.level = 0
    switch.last_level.return_value = 0

    led = mock_lutron.areas[0].keypads[0].leds[0]
    led.state = 0
    led.last_state = 0

    assert await async_setup_component(hass, "lutron", {})
    await hass.async_block_till_done()

    # Test Switch
    state = hass.states.get("switch.test_switch")
    assert state is not None
    assert state.state == STATE_OFF

    # Test LED
    state = hass.states.get("switch.test_keypad_test_button")
    assert state is not None
    assert state.state == STATE_OFF


async def test_switch_turn_on_off(
    hass: HomeAssistant, mock_lutron: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test switch turn on and off."""
    mock_config_entry.add_to_hass(hass)

    switch = mock_lutron.areas[0].outputs[1]
    switch.level = 0
    switch.last_level.return_value = 0

    assert await async_setup_component(hass, "lutron", {})
    await hass.async_block_till_done()

    entity_id = "switch.test_switch"

    # Turn on
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert switch.level == 100

    # Turn off
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert switch.level == 0


async def test_led_turn_on_off(
    hass: HomeAssistant, mock_lutron: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test LED turn on and off."""
    mock_config_entry.add_to_hass(hass)

    led = mock_lutron.areas[0].keypads[0].leds[0]
    led.state = 0
    led.last_state = 0

    assert await async_setup_component(hass, "lutron", {})
    await hass.async_block_till_done()

    entity_id = "switch.test_keypad_test_button"

    # Turn on
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert led.state == 1

    # Turn off
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert led.state == 0
