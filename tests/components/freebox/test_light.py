"""Tests for the Freebox lights."""

from copy import deepcopy
from unittest.mock import Mock

from homeassistant.components.freebox.light import LED_STRIP_BRIGHTNESS_SCALE
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.util.color import value_to_brightness

from .common import setup_platform
from .const import DATA_LCD_GET_CONFIGURATION


async def test_light_led_strip_value(hass: HomeAssistant, router: Mock) -> None:
    """Test that the LED Strip entity exists and has the right value and attributes."""
    await setup_platform(hass, LIGHT_DOMAIN)

    entity = hass.states.get("light.freebox_led_strip")
    assert entity is not None
    assert entity.state == "on"
    expected_brightness = value_to_brightness(
        LED_STRIP_BRIGHTNESS_SCALE, DATA_LCD_GET_CONFIGURATION["led_strip_brightness"]
    )
    assert entity.attributes["brightness"] == expected_brightness
    assert (
        entity.attributes["effect"] == DATA_LCD_GET_CONFIGURATION["led_strip_animation"]
    )


async def test_light_no_led_strip_on_unsupported(
    hass: HomeAssistant, router: Mock
) -> None:
    """Test that the LED Strip entity doesn't exist on unsupported hardware."""
    new_lcd_config = deepcopy(DATA_LCD_GET_CONFIGURATION)
    keys_to_remove = (
        "led_strip_enabled",
        "led_strip_brightness",
        "led_strip_animation",
        "available_led_strip_animations",
    )
    for k in keys_to_remove:
        new_lcd_config.pop(k, None)
    router().lcd.get_configuration.return_value = new_lcd_config

    await setup_platform(hass, LIGHT_DOMAIN)

    assert hass.states.get("light.freebox_led_strip") is None
