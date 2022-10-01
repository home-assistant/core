"""Support for Nanoleaf Lights."""
from __future__ import annotations

import math
from typing import Any

from aionanoleaf import Nanoleaf

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util.color import (
    color_temperature_kelvin_to_mired as kelvin_to_mired,
    color_temperature_mired_to_kelvin as mired_to_kelvin,
)

from . import NanoleafEntryData
from .const import DOMAIN
from .entity import NanoleafEntity

RESERVED_EFFECTS = ("*Solid*", "*Static*", "*Dynamic*")
DEFAULT_NAME = "Nanoleaf"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Nanoleaf light."""
    entry_data: NanoleafEntryData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([NanoleafLight(entry_data.device, entry_data.coordinator)])


class NanoleafLight(NanoleafEntity, LightEntity):
    """Representation of a Nanoleaf Light."""

    _attr_supported_color_modes = {ColorMode.COLOR_TEMP, ColorMode.HS}
    _attr_supported_features = LightEntityFeature.EFFECT | LightEntityFeature.TRANSITION

    def __init__(self, nanoleaf: Nanoleaf, coordinator: DataUpdateCoordinator) -> None:
        """Initialize the Nanoleaf light."""
        super().__init__(nanoleaf, coordinator)
        self._attr_unique_id = nanoleaf.serial_no
        self._attr_name = nanoleaf.name
        self._attr_min_mireds = math.ceil(1000000 / nanoleaf.color_temperature_max)
        self._attr_max_mireds = kelvin_to_mired(nanoleaf.color_temperature_min)

    @property
    def brightness(self) -> int:
        """Return the brightness of the light."""
        return int(self._nanoleaf.brightness * 2.55)

    @property
    def color_temp(self) -> int:
        """Return the current color temperature."""
        return kelvin_to_mired(self._nanoleaf.color_temperature)

    @property
    def effect(self) -> str | None:
        """Return the current effect."""
        # The API returns the *Solid* effect if the Nanoleaf is in HS or CT mode.
        # The effects *Static* and *Dynamic* are not supported by Home Assistant.
        # These reserved effects are implicitly set and are not in the effect_list.
        # https://forum.nanoleaf.me/docs/openapi#_byoot0bams8f
        return (
            None if self._nanoleaf.effect in RESERVED_EFFECTS else self._nanoleaf.effect
        )

    @property
    def effect_list(self) -> list[str]:
        """Return the list of supported effects."""
        return self._nanoleaf.effects_list

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend, if any."""
        return "mdi:triangle-outline"

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self._nanoleaf.is_on

    @property
    def hs_color(self) -> tuple[int, int]:
        """Return the color in HS."""
        return self._nanoleaf.hue, self._nanoleaf.saturation

    @property
    def color_mode(self) -> ColorMode | None:
        """Return the color mode of the light."""
        # According to API docs, color mode is "ct", "effect" or "hs"
        # https://forum.nanoleaf.me/docs/openapi#_4qgqrz96f44d
        if self._nanoleaf.color_mode == "ct":
            return ColorMode.COLOR_TEMP
        # Home Assistant does not have an "effect" color mode, just report hs
        return ColorMode.HS

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        hs_color = kwargs.get(ATTR_HS_COLOR)
        color_temp_mired = kwargs.get(ATTR_COLOR_TEMP)
        effect = kwargs.get(ATTR_EFFECT)
        transition = kwargs.get(ATTR_TRANSITION)

        if effect:
            if effect not in self.effect_list:
                raise ValueError(
                    f"Attempting to apply effect not in the effect list: '{effect}'"
                )
            await self._nanoleaf.set_effect(effect)
        elif hs_color:
            hue, saturation = hs_color
            await self._nanoleaf.set_hue(int(hue))
            await self._nanoleaf.set_saturation(int(saturation))
        elif color_temp_mired:
            await self._nanoleaf.set_color_temperature(
                mired_to_kelvin(color_temp_mired)
            )
        if transition:
            if brightness:  # tune to the required brightness in n seconds
                await self._nanoleaf.set_brightness(
                    int(brightness / 2.55), transition=int(kwargs[ATTR_TRANSITION])
                )
            else:  # If brightness is not specified, assume full brightness
                await self._nanoleaf.set_brightness(100, transition=int(transition))
        else:  # If no transition is occurring, turn on the light
            await self._nanoleaf.turn_on()
            if brightness:
                await self._nanoleaf.set_brightness(int(brightness / 2.55))

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        transition: float | None = kwargs.get(ATTR_TRANSITION)
        await self._nanoleaf.turn_off(None if transition is None else int(transition))
