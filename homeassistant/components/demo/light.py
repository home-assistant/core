"""Demo light platform that implements lights."""

from __future__ import annotations

import random
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ATTR_WHITE,
    DEFAULT_MAX_KELVIN,
    DEFAULT_MIN_KELVIN,
    EFFECT_OFF,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DOMAIN

LIGHT_COLORS = [(56, 86), (345, 75)]

LIGHT_EFFECT_LIST = ["rainbow", EFFECT_OFF]

LIGHT_TEMPS = [4166, 2631]

SUPPORT_DEMO = {ColorMode.HS, ColorMode.COLOR_TEMP}
SUPPORT_DEMO_HS_WHITE = {ColorMode.HS, ColorMode.WHITE}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the demo light platform."""
    async_add_entities(
        [
            DemoLight(
                effect_list=LIGHT_EFFECT_LIST,
                effect=LIGHT_EFFECT_LIST[0],
                translation_key="bed_light",
                device_name="Bed Light",
                state=False,
                unique_id="light_1",
            ),
            DemoLight(
                ct=LIGHT_TEMPS[1],
                device_name="Ceiling Lights",
                state=True,
                unique_id="light_2",
            ),
            DemoLight(
                hs_color=LIGHT_COLORS[1],
                device_name="Kitchen Lights",
                state=True,
                unique_id="light_3",
            ),
            DemoLight(
                ct=LIGHT_TEMPS[1],
                device_name="Office RGBW Lights",
                rgbw_color=(255, 0, 0, 255),
                state=True,
                supported_color_modes={ColorMode.RGBW},
                unique_id="light_4",
            ),
            DemoLight(
                device_name="Living Room RGBWW Lights",
                rgbww_color=(255, 0, 0, 255, 0),
                state=True,
                supported_color_modes={ColorMode.RGBWW},
                unique_id="light_5",
            ),
            DemoLight(
                device_name="Entrance Color + White Lights",
                hs_color=LIGHT_COLORS[1],
                state=True,
                supported_color_modes=SUPPORT_DEMO_HS_WHITE,
                unique_id="light_6",
            ),
        ]
    )


class DemoLight(LightEntity):
    """Representation of a demo light."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False

    _attr_max_color_temp_kelvin = DEFAULT_MAX_KELVIN
    _attr_min_color_temp_kelvin = DEFAULT_MIN_KELVIN

    def __init__(
        self,
        unique_id: str,
        device_name: str,
        state: bool,
        brightness: int = 180,
        ct: int | None = None,
        effect_list: list[str] | None = None,
        effect: str | None = None,
        hs_color: tuple[int, int] | None = None,
        rgbw_color: tuple[int, int, int, int] | None = None,
        rgbww_color: tuple[int, int, int, int, int] | None = None,
        supported_color_modes: set[ColorMode] | None = None,
        translation_key: str | None = None,
    ) -> None:
        """Initialize the light."""
        self._attr_translation_key = translation_key
        self._attr_brightness = brightness
        self._attr_color_temp_kelvin = ct or random.choice(LIGHT_TEMPS)
        self._attr_effect = effect
        self._attr_effect_list = effect_list
        self._attr_hs_color = hs_color
        self._attr_rgbw_color = rgbw_color
        self._attr_rgbww_color = rgbww_color
        self._attr_is_on = state
        self._attr_unique_id = unique_id
        if hs_color:
            self._attr_color_mode = ColorMode.HS
        elif rgbw_color:
            self._attr_color_mode = ColorMode.RGBW
        elif rgbww_color:
            self._attr_color_mode = ColorMode.RGBWW
        else:
            self._attr_color_mode = ColorMode.COLOR_TEMP
        if not supported_color_modes:
            supported_color_modes = SUPPORT_DEMO
        self._attr_supported_color_modes = supported_color_modes
        if self._attr_effect_list is not None:
            self._attr_supported_features |= LightEntityFeature.EFFECT
        self._attr_device_info = DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, unique_id)
            },
            name=device_name,
        )

    @property
    def available(self) -> bool:
        """Return availability."""
        # This demo light is always available, but well-behaving components
        # should implement this to inform Home Assistant accordingly.
        return True

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        self._attr_is_on = True

        if ATTR_BRIGHTNESS in kwargs:
            self._attr_brightness = kwargs[ATTR_BRIGHTNESS]

        if ATTR_COLOR_TEMP_KELVIN in kwargs:
            self._attr_color_mode = ColorMode.COLOR_TEMP
            self._attr_color_temp_kelvin = kwargs[ATTR_COLOR_TEMP_KELVIN]

        if ATTR_EFFECT in kwargs:
            self._attr_effect = kwargs[ATTR_EFFECT]

        if ATTR_HS_COLOR in kwargs:
            self._attr_color_mode = ColorMode.HS
            self._attr_hs_color = kwargs[ATTR_HS_COLOR]

        if ATTR_RGBW_COLOR in kwargs:
            self._attr_color_mode = ColorMode.RGBW
            self._attr_rgbw_color = kwargs[ATTR_RGBW_COLOR]

        if ATTR_RGBWW_COLOR in kwargs:
            self._attr_color_mode = ColorMode.RGBWW
            self._attr_rgbww_color = kwargs[ATTR_RGBWW_COLOR]

        if ATTR_WHITE in kwargs:
            self._attr_color_mode = ColorMode.WHITE
            self._attr_brightness = kwargs[ATTR_WHITE]

        # As we have disabled polling, we need to inform
        # Home Assistant about updates in our state ourselves.
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        self._attr_is_on = False

        # As we have disabled polling, we need to inform
        # Home Assistant about updates in our state ourselves.
        self.async_write_ha_state()
