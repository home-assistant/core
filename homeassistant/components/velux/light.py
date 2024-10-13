"""Support for Velux lights."""

from __future__ import annotations

from typing import Any

from pyvlx import Intensity, LighteningDevice

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import VeluxEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant, config: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up light(s) for Velux platform."""
    module = hass.data[DOMAIN][config.entry_id]

    async_add_entities(
        VeluxLight(node, config.entry_id)
        for node in module.pyvlx.nodes
        if isinstance(node, LighteningDevice)
    )


class VeluxLight(VeluxEntity, LightEntity):
    """Representation of a Velux light."""

    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_color_mode = ColorMode.BRIGHTNESS

    node: LighteningDevice

    @property
    def brightness(self):
        """Return the current brightness."""
        return int((100 - self.node.intensity.intensity_percent) * 255 / 100)

    @property
    def is_on(self):
        """Return true if light is on."""
        return not self.node.intensity.off and self.node.intensity.known

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        if ATTR_BRIGHTNESS in kwargs:
            intensity_percent = int(100 - kwargs[ATTR_BRIGHTNESS] / 255 * 100)
            await self.node.set_intensity(
                Intensity(intensity_percent=intensity_percent),
                wait_for_completion=True,
            )
        else:
            await self.node.turn_on(wait_for_completion=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        await self.node.turn_off(wait_for_completion=True)
