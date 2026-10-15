"""Support for Dynalite channels as lights."""

from typing import Any, override

from homeassistant.components.light import (
    ColorMode,
    LightEntity,
    LightEntityStateAttribute,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .bridge import DynaliteConfigEntry
from .entity import DynaliteBase, async_setup_entry_base


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DynaliteConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Record the async_add_entities function to add them later."""
    async_setup_entry_base(
        hass, config_entry, async_add_entities, "light", DynaliteLight
    )


class DynaliteLight(DynaliteBase, LightEntity):
    """Representation of a Dynalite Channel as a Home Assistant Light."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    @property
    @override
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        return self._device.brightness

    @property
    @override
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._device.is_on

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        await self._device.async_turn_on(**kwargs)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self._device.async_turn_off(**kwargs)

    @override
    def initialize_state(self, state):
        """Initialize the state from cache."""
        target_level = state.attributes.get(LightEntityStateAttribute.BRIGHTNESS)
        if target_level is not None:
            self._device.init_level(target_level)
