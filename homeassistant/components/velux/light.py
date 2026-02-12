"""Support for Velux lights."""

from __future__ import annotations

from typing import Any

from pyvlx import Intensity, Light, OnOffLight

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VeluxConfigEntry
from .entity import VeluxEntity, wrap_pyvlx_call_exceptions

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VeluxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up light(s) for Velux platform."""
    pyvlx = config_entry.runtime_data
    async_add_entities(
        VeluxLight(node, config_entry.entry_id)
        for node in pyvlx.nodes
        if isinstance(node, (Light, OnOffLight))
    )


class VeluxLight(VeluxEntity, LightEntity):
    """Representation of a Velux light."""

    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_name = None

    node: Light

    @property
    def brightness(self):
        """Return the current brightness."""
        return int(self.node.intensity.intensity_percent * 255 / 100)

    @property
    def is_on(self):
        """Return true if light is on."""
        return not self.node.intensity.off and self.node.intensity.known

    @wrap_pyvlx_call_exceptions
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        if ATTR_BRIGHTNESS in kwargs:
            intensity_percent = int(kwargs[ATTR_BRIGHTNESS] / 255 * 100)
            await self.node.set_intensity(
                Intensity(intensity_percent=intensity_percent),
                wait_for_completion=True,
            )
        else:
            await self.node.turn_on(wait_for_completion=True)

    @wrap_pyvlx_call_exceptions
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        await self.node.turn_off(wait_for_completion=True)
