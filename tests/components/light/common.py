"""Collection of helper methods.

All containing methods are legacy helpers that should not be used by new
components. Instead call the service directly.
"""
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_BRIGHTNESS_PCT, ATTR_COLOR_NAME, ATTR_COLOR_TEMP,
    ATTR_EFFECT, ATTR_FLASH, ATTR_HS_COLOR, ATTR_KELVIN, ATTR_PROFILE,
    ATTR_RGB_COLOR, ATTR_TRANSITION, ATTR_WHITE_VALUE, ATTR_XY_COLOR, DOMAIN)
from homeassistant.const import (
    ATTR_ENTITY_ID, SERVICE_TOGGLE, SERVICE_TURN_OFF, SERVICE_TURN_ON)
from homeassistant.core import callback
from homeassistant.loader import bind_hass


@bind_hass
def turn_on(hass, entity_id=None, transition=None, brightness=None,
            brightness_pct=None, rgb_color=None, xy_color=None, hs_color=None,
            color_temp=None, kelvin=None, white_value=None,
            profile=None, flash=None, effect=None, color_name=None):
    """Turn all or specified light on."""
    hass.add_job(
        async_turn_on, hass, entity_id, transition, brightness, brightness_pct,
        rgb_color, xy_color, hs_color, color_temp, kelvin, white_value,
        profile, flash, effect, color_name)


@callback
@bind_hass
def async_turn_on(hass, entity_id=None, transition=None, brightness=None,
                  brightness_pct=None, rgb_color=None, xy_color=None,
                  hs_color=None, color_temp=None, kelvin=None,
                  white_value=None, profile=None, flash=None, effect=None,
                  color_name=None):
    """Turn all or specified light on."""
    data = {
        key: value for key, value in [
            (ATTR_ENTITY_ID, entity_id),
            (ATTR_PROFILE, profile),
            (ATTR_TRANSITION, transition),
            (ATTR_BRIGHTNESS, brightness),
            (ATTR_BRIGHTNESS_PCT, brightness_pct),
            (ATTR_RGB_COLOR, rgb_color),
            (ATTR_XY_COLOR, xy_color),
            (ATTR_HS_COLOR, hs_color),
            (ATTR_COLOR_TEMP, color_temp),
            (ATTR_KELVIN, kelvin),
            (ATTR_WHITE_VALUE, white_value),
            (ATTR_FLASH, flash),
            (ATTR_EFFECT, effect),
            (ATTR_COLOR_NAME, color_name),
        ] if value is not None
    }

    hass.async_add_job(hass.services.async_call(DOMAIN, SERVICE_TURN_ON, data))


@bind_hass
def turn_off(hass, entity_id=None, transition=None):
    """Turn all or specified light off."""
    hass.add_job(async_turn_off, hass, entity_id, transition)


@callback
@bind_hass
def async_turn_off(hass, entity_id=None, transition=None):
    """Turn all or specified light off."""
    data = {
        key: value for key, value in [
            (ATTR_ENTITY_ID, entity_id),
            (ATTR_TRANSITION, transition),
        ] if value is not None
    }

    hass.async_add_job(hass.services.async_call(
        DOMAIN, SERVICE_TURN_OFF, data))


@bind_hass
def toggle(hass, entity_id=None, transition=None):
    """Toggle all or specified light."""
    hass.add_job(async_toggle, hass, entity_id, transition)


@callback
@bind_hass
def async_toggle(hass, entity_id=None, transition=None):
    """Toggle all or specified light."""
    data = {
        key: value for key, value in [
            (ATTR_ENTITY_ID, entity_id),
            (ATTR_TRANSITION, transition),
        ] if value is not None
    }

    hass.async_add_job(hass.services.async_call(
        DOMAIN, SERVICE_TOGGLE, data))
