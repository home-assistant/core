"""Support for Duotecno lights."""

from typing import Any

from duotecno.unit import DimUnit

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DuotecnoConfigEntry
from .entity import DuotecnoEntity, api_call


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DuotecnoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Duotecno light based on config_entry."""
    async_add_entities(
        DuotecnoLight(channel) for channel in entry.runtime_data.get_units("DimUnit")
    )


class DuotecnoLight(DuotecnoEntity, LightEntity):
    """Representation of a light."""

    _unit: DimUnit
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    @property
    def is_on(self) -> bool:
        """Return true if the light is on."""
        return self._unit.is_on()

    @property
    def brightness(self) -> int:
        """Return the brightness of the light."""
        return int((self._unit.get_dimmer_state() * 255) / 100)

    @api_call
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        if (val := kwargs.get(ATTR_BRIGHTNESS)) is not None:
            # set to a value
            val = max(int((val * 100) / 255), 1)
        else:
            # restore state
            val = None
        await self._unit.set_dimmer_state(val)

    @api_call
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        await self._unit.set_dimmer_state(0)
