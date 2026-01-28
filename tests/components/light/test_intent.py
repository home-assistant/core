"""Tests for the light intents."""

import pytest

from homeassistant.components import light
from homeassistant.components.light import ATTR_SUPPORTED_COLOR_MODES, ColorMode, intent
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.intent import InvalidSlotInfo, async_handle

from tests.common import async_mock_service


async def test_intent_set_color(hass: HomeAssistant) -> None:
    """Test the set color intent."""
    hass.states.async_set(
        "light.hello_2", "off", {ATTR_SUPPORTED_COLOR_MODES: [ColorMode.HS]}
    )
    hass.states.async_set("switch.hello", "off")
    calls = async_mock_service(hass, light.DOMAIN, light.SERVICE_TURN_ON)
    await intent.async_setup_intents(hass)

    await async_handle(
        hass,
        "test",
        intent.INTENT_SET,
        {"name": {"value": "Hello 2"}, "color": {"value": "blue"}},
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    call = calls[0]
    assert call.domain == light.DOMAIN
    assert call.service == SERVICE_TURN_ON
    assert call.data.get(ATTR_ENTITY_ID) == "light.hello_2"
    assert call.data.get(light.ATTR_RGB_COLOR) == (0, 0, 255)


async def test_intent_set_color_and_brightness(hass: HomeAssistant) -> None:
    """Test the set color intent."""
    hass.states.async_set(
        "light.hello_2", "off", {ATTR_SUPPORTED_COLOR_MODES: [ColorMode.HS]}
    )
    hass.states.async_set("switch.hello", "off")
    calls = async_mock_service(hass, light.DOMAIN, light.SERVICE_TURN_ON)
    await intent.async_setup_intents(hass)

    await async_handle(
        hass,
        "test",
        intent.INTENT_SET,
        {
            "name": {"value": "Hello 2"},
            "color": {"value": "blue"},
            "brightness": {"value": "20"},
        },
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    call = calls[0]
    assert call.domain == light.DOMAIN
    assert call.service == SERVICE_TURN_ON
    assert call.data.get(ATTR_ENTITY_ID) == "light.hello_2"
    assert call.data.get(light.ATTR_RGB_COLOR) == (0, 0, 255)
    assert call.data.get(light.ATTR_BRIGHTNESS_PCT) == 20


async def test_intent_set_temperature(hass: HomeAssistant) -> None:
    """Test setting the color temperature in kevin via intent."""
    hass.states.async_set(
        "light.test", "off", {ATTR_SUPPORTED_COLOR_MODES: [ColorMode.COLOR_TEMP]}
    )
    calls = async_mock_service(hass, light.DOMAIN, light.SERVICE_TURN_ON)
    await intent.async_setup_intents(hass)

    await async_handle(
        hass,
        "test",
        intent.INTENT_SET,
        {
            "name": {"value": "Test"},
            "temperature": {"value": 2000},
        },
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    call = calls[0]
    assert call.domain == light.DOMAIN
    assert call.service == SERVICE_TURN_ON
    assert call.data.get(ATTR_ENTITY_ID) == "light.test"
    assert call.data.get(light.ATTR_COLOR_TEMP_KELVIN) == 2000


async def test_intent_set_missing_required_slots(hass: HomeAssistant) -> None:
    """Test that the intent fails when none of the required slots (color, temperature, brightness) are provided."""
    hass.states.async_set(
        "light.test", "off", {ATTR_SUPPORTED_COLOR_MODES: [ColorMode.HS]}
    )
    calls = async_mock_service(hass, light.DOMAIN, light.SERVICE_TURN_ON)
    await intent.async_setup_intents(hass)

    # Test with only name - should fail because none of color, temperature, brightness are provided
    with pytest.raises(InvalidSlotInfo) as exc_info:
        await async_handle(
            hass,
            "test",
            intent.INTENT_SET,
            {"name": {"value": "Test"}},
        )

    # Verify the error message indicates that at least one of the required slots is needed
    error_message = str(exc_info.value)
    assert (
        "color" in error_message
        or "temperature" in error_message
        or "brightness" in error_message
    )

    # Test with empty slots - should also fail
    with pytest.raises(InvalidSlotInfo) as exc_info:
        await async_handle(
            hass,
            "test",
            intent.INTENT_SET,
            {},
        )

    # Verify no service calls were made since validation failed
    assert len(calls) == 0


async def test_intent_set_with_required_slots_passes(hass: HomeAssistant) -> None:
    """Test that the intent succeeds when at least one required slot is provided."""
    hass.states.async_set(
        "light.test", "off", {ATTR_SUPPORTED_COLOR_MODES: [ColorMode.BRIGHTNESS]}
    )
    calls = async_mock_service(hass, light.DOMAIN, light.SERVICE_TURN_ON)
    await intent.async_setup_intents(hass)

    # Test with brightness only - should pass
    await async_handle(
        hass,
        "test",
        intent.INTENT_SET,
        {
            "name": {"value": "Test"},
            "brightness": {"value": "50"},
        },
    )
    await hass.async_block_till_done()

    # Verify service was called successfully
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == light.DOMAIN
    assert call.service == SERVICE_TURN_ON
    assert call.data.get(ATTR_ENTITY_ID) == "light.test"
    assert call.data.get(light.ATTR_BRIGHTNESS_PCT) == 50
