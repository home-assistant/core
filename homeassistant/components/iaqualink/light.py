"""Support for Aqualink pool lights."""

from __future__ import annotations

from typing import Any

from iaqualink.device import AqualinkLight

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    DOMAIN as LIGHT_DOMAIN,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import refresh_system
from .const import DOMAIN
from .entity import AqualinkEntity
from .utils import await_or_reraise

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up discovered lights."""
    async_add_entities(
        (HassAqualinkLight(dev) for dev in hass.data[DOMAIN][LIGHT_DOMAIN]),
        True,
    )


class HassAqualinkLight(AqualinkEntity[AqualinkLight], LightEntity):
    """Representation of a light."""

    def __init__(self, dev: AqualinkLight) -> None:
        """Initialize AquaLink light."""
        super().__init__(dev)
        self._attr_name = dev.label
        if dev.supports_effect:
            self._attr_effect_list = list(dev.supported_effects)
            self._attr_supported_features = LightEntityFeature.EFFECT
        color_mode = ColorMode.ONOFF
        if dev.supports_brightness:
            color_mode = ColorMode.BRIGHTNESS
        self._attr_color_mode = color_mode
        self._attr_supported_color_modes = {color_mode}

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
