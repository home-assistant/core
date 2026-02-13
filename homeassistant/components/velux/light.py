"""Support for Velux lights."""

from __future__ import annotations

from typing import Any

from pyvlx import DimmableDevice, Intensity, Light, OnOffLight

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
    entities: list[VeluxOnOffLight] = []
    for node in pyvlx.nodes:
        if isinstance(node, Light):
            entities.append(VeluxDimmableLight(node, config_entry.entry_id))
        elif isinstance(node, OnOffLight):
            entities.append(VeluxOnOffLight(node, config_entry.entry_id))
    async_add_entities(entities)


class VeluxOnOffLight(VeluxEntity, LightEntity):
    """Representation of a Velux light without brightness control."""

    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_color_mode = ColorMode.ONOFF
    _attr_name = None

    node: DimmableDevice

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return not self.node.intensity.off and self.node.intensity.known

    @wrap_pyvlx_call_exceptions
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        await self.node.turn_on(wait_for_completion=True)

    @wrap_pyvlx_call_exceptions
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        await self.node.turn_off(wait_for_completion=True)


class VeluxDimmableLight(VeluxOnOffLight):
    """Representation of a Velux light with brightness control."""

    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_name = None

    @property
    def brightness(self) -> int:
        """Return the current brightness."""
        return int(self.node.intensity.intensity_percent * 255 / 100)

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
