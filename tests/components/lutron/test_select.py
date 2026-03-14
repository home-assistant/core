"""Tests for the Lutron select platform."""

from unittest.mock import MagicMock

from pylutron import Led

from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_OPTION
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_led_select_setup(
    hass: HomeAssistant, mock_lutron: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test the setup of Lutron LED select entities."""
    mock_config_entry.add_to_hass(hass)

    assert await async_setup_component(hass, "lutron", {})
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get("select.test_keypad_test_button_led")
    assert entry.unique_id == "12345678901_led_uuid"

    state = hass.states.get("select.test_keypad_test_button_led")
    assert state is not None
    assert state.state == "Off"
    assert state.attributes["options"] == ["Off", "On", "Slow Flash", "Fast Flash"]


async def test_led_select_option(
    hass: HomeAssistant, mock_lutron: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test selecting an option for a Lutron LED select entity."""
    mock_config_entry.add_to_hass(hass)

    assert await async_setup_component(hass, "lutron", {})
    await hass.async_block_till_done()

    led = mock_lutron.areas[0].keypads[0].leds[0]
    # Set up the mock to act like a real object for 'state'
    type(led).state = Led.LED_OFF

    # Select "On"
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: "select.test_keypad_test_button_led", ATTR_OPTION: "On"},
        blocking=True,
    )
    assert led.state == Led.LED_ON

    # Select "Slow Flash"
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.test_keypad_test_button_led",
            ATTR_OPTION: "Slow Flash",
        },
        blocking=True,
    )
    assert led.state == Led.LED_SLOW_FLASH
