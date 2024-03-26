"""Collection of helper methods.

All containing methods are legacy helpers that should not be used by new
components. Instead call the service directly.
"""

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_BRIGHTNESS_PCT,
    ATTR_COLOR_NAME,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_FLASH,
    ATTR_HS_COLOR,
    ATTR_KELVIN,
    ATTR_PROFILE,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ATTR_TRANSITION,
    ATTR_WHITE,
    ATTR_XY_COLOR,
    DOMAIN,
    ColorMode,
    LightEntity,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ENTITY_MATCH_ALL,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.loader import bind_hass

from tests.common import MockToggleEntity


@bind_hass
def turn_on(
    hass,
    entity_id=ENTITY_MATCH_ALL,
    transition=None,
    brightness=None,
    brightness_pct=None,
    rgb_color=None,
    rgbw_color=None,
    rgbww_color=None,
    xy_color=None,
    hs_color=None,
    color_temp=None,
    kelvin=None,
    profile=None,
    flash=None,
    effect=None,
    color_name=None,
    white=None,
):
    """Turn all or specified light on."""
    hass.add_job(
        async_turn_on,
        hass,
        entity_id,
        transition,
        brightness,
        brightness_pct,
        rgb_color,
        rgbw_color,
        rgbww_color,
        xy_color,
        hs_color,
        color_temp,
        kelvin,
        profile,
        flash,
        effect,
        color_name,
        white,
    )


async def async_turn_on(
    hass,
    entity_id=ENTITY_MATCH_ALL,
    transition=None,
    brightness=None,
    brightness_pct=None,
    rgb_color=None,
    rgbw_color=None,
    rgbww_color=None,
    xy_color=None,
    hs_color=None,
    color_temp=None,
    kelvin=None,
    profile=None,
    flash=None,
    effect=None,
    color_name=None,
    white=None,
):
    """Turn all or specified light on."""
    data = {
        key: value
        for key, value in [
            (ATTR_ENTITY_ID, entity_id),
            (ATTR_PROFILE, profile),
            (ATTR_TRANSITION, transition),
            (ATTR_BRIGHTNESS, brightness),
            (ATTR_BRIGHTNESS_PCT, brightness_pct),
            (ATTR_RGB_COLOR, rgb_color),
            (ATTR_RGBW_COLOR, rgbw_color),
            (ATTR_RGBWW_COLOR, rgbww_color),
            (ATTR_XY_COLOR, xy_color),
            (ATTR_HS_COLOR, hs_color),
            (ATTR_COLOR_TEMP, color_temp),
            (ATTR_KELVIN, kelvin),
            (ATTR_FLASH, flash),
            (ATTR_EFFECT, effect),
            (ATTR_COLOR_NAME, color_name),
            (ATTR_WHITE, white),
        ]
        if value is not None
    }

    await hass.services.async_call(DOMAIN, SERVICE_TURN_ON, data, blocking=True)


@bind_hass
def turn_off(hass, entity_id=ENTITY_MATCH_ALL, transition=None, flash=None):
    """Turn all or specified light off."""
    hass.add_job(async_turn_off, hass, entity_id, transition, flash)


async def async_turn_off(hass, entity_id=ENTITY_MATCH_ALL, transition=None, flash=None):
    """Turn all or specified light off."""
    data = {
        key: value
        for key, value in [
            (ATTR_ENTITY_ID, entity_id),
            (ATTR_TRANSITION, transition),
            (ATTR_FLASH, flash),
        ]
        if value is not None
    }

    await hass.services.async_call(DOMAIN, SERVICE_TURN_OFF, data, blocking=True)


@bind_hass
def toggle(
    hass,
    entity_id=ENTITY_MATCH_ALL,
    transition=None,
    brightness=None,
    brightness_pct=None,
    rgb_color=None,
    xy_color=None,
    hs_color=None,
    color_temp=None,
    kelvin=None,
    profile=None,
    flash=None,
    effect=None,
    color_name=None,
):
    """Toggle all or specified light."""
    hass.add_job(
        async_toggle,
        hass,
        entity_id,
        transition,
        brightness,
        brightness_pct,
        rgb_color,
        xy_color,
        hs_color,
        color_temp,
        kelvin,
        profile,
        flash,
        effect,
        color_name,
    )


async def async_toggle(
    hass,
    entity_id=ENTITY_MATCH_ALL,
    transition=None,
    brightness=None,
    brightness_pct=None,
    rgb_color=None,
    xy_color=None,
    hs_color=None,
    color_temp=None,
    kelvin=None,
    profile=None,
    flash=None,
    effect=None,
    color_name=None,
):
    """Turn all or specified light on."""
    data = {
        key: value
        for key, value in [
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
            (ATTR_FLASH, flash),
            (ATTR_EFFECT, effect),
            (ATTR_COLOR_NAME, color_name),
        ]
        if value is not None
    }

    await hass.services.async_call(DOMAIN, SERVICE_TOGGLE, data, blocking=True)


TURN_ON_ARG_TO_COLOR_MODE = {
    "hs_color": ColorMode.HS,
    "xy_color": ColorMode.XY,
    "rgb_color": ColorMode.RGB,
    "rgbw_color": ColorMode.RGBW,
    "rgbww_color": ColorMode.RGBWW,
    "color_temp_kelvin": ColorMode.COLOR_TEMP,
}


class MockLight(MockToggleEntity, LightEntity):
    """Mock light class."""

    _attr_max_color_temp_kelvin = 6500
    _attr_min_color_temp_kelvin = 2000
    supported_features = 0

    brightness = None
    color_temp_kelvin = None
    hs_color = None
    rgb_color = None
    rgbw_color = None
    rgbww_color = None
    xy_color = None

    def __init__(
        self,
        name,
        state,
        unique_id=None,
        supported_color_modes: set[ColorMode] | None = None,
    ):
        """Initialize the mock light."""
        super().__init__(name, state, unique_id)
        if supported_color_modes is None:
            supported_color_modes = {ColorMode.ONOFF}
        self._attr_supported_color_modes = supported_color_modes
        color_mode = ColorMode.UNKNOWN
        if len(supported_color_modes) == 1:
            color_mode = next(iter(supported_color_modes))
        self._attr_color_mode = color_mode

    def turn_on(self, **kwargs):
        """Turn the entity on."""
        super().turn_on(**kwargs)
        for key, value in kwargs.items():
            if key in [
                "brightness",
                "hs_color",
                "xy_color",
                "rgb_color",
                "rgbw_color",
                "rgbww_color",
                "color_temp_kelvin",
            ]:
                setattr(self, key, value)
            if key == "white":
                setattr(self, "brightness", value)
            if key in TURN_ON_ARG_TO_COLOR_MODE:
                self._attr_color_mode = TURN_ON_ARG_TO_COLOR_MODE[key]
