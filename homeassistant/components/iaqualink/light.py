"""Support for Aqualink pool lights."""
from __future__ import annotations

from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    DOMAIN,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AqualinkEntity, refresh_system
from .const import DOMAIN as AQUALINK_DOMAIN
from .utils import await_or_reraise

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up discovered lights."""
    devs = []
    for dev in hass.data[AQUALINK_DOMAIN][DOMAIN]:
        devs.append(HassAqualinkLight(dev))
    async_add_entities(devs, True)


class HassAqualinkLight(AqualinkEntity, LightEntity):
    """Representation of a light."""

    @property
    def name(self) -> str:
        """Return the name of the light."""
        return self.dev.label

    @property
    def is_on(self) -> bool:
        """Return whether the light is on or off."""
        return self.dev.is_on

    @refresh_system
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light.

        This handles brightness and light effects for lights that do support
        them.
        """
        # For now I'm assuming lights support either effects or brightness.
        if effect_name := kwargs.get(ATTR_EFFECT):
            await await_or_reraise(self.dev.set_effect_by_name(effect_name))
        elif brightness := kwargs.get(ATTR_BRIGHTNESS):
            # Aqualink supports percentages in 25% increments.
            pct = int(round(brightness * 4.0 / 255)) * 25
            await await_or_reraise(self.dev.set_brightness(pct))
        else:
            await await_or_reraise(self.dev.turn_on())

    @refresh_system
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        await await_or_reraise(self.dev.turn_off())

    @property
    def brightness(self) -> int:
        """Return current brightness of the light.

        The scale needs converting between 0-100 and 0-255.
        """
        return self.dev.brightness * 255 / 100

    @property
    def effect(self) -> str:
        """Return the current light effect if supported."""
        return self.dev.effect

    @property
    def effect_list(self) -> list:
        """Return supported light effects."""
        return list(self.dev.supported_effects)

    @property
    def color_mode(self) -> ColorMode:
        """Return the color mode of the light."""
        if self.dev.supports_brightness:
            return ColorMode.BRIGHTNESS
        return ColorMode.ONOFF

    @property
    def supported_color_modes(self) -> set[ColorMode]:
        """Flag supported color modes."""
        return {self.color_mode}

    @property
    def supported_features(self) -> LightEntityFeature:
        """Return the list of features supported by the light."""
        if self.dev.supports_effect:
            return LightEntityFeature.EFFECT

        return LightEntityFeature(0)
