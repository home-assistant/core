"""Support for Velux lights."""
from __future__ import annotations

import logging
from typing import Any

from pyvlx import Intensity, PyVLX
from pyvlx.lightening_device import Light

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .node_entity import VeluxNodeEntity

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up light(s) for Velux platform."""
    entities = []
    pyvlx: PyVLX = hass.data[DOMAIN][entry.entry_id]
    for node in pyvlx.nodes:
        if isinstance(node, Light):
            _LOGGER.debug("Light will be added: %s", node.name)
            entities.append(VeluxLight(node))
    async_add_entities(entities)


class VeluxLight(VeluxNodeEntity, LightEntity):
    """Representation of a Velux light."""

    def __init__(self, node: Light) -> None:
        """Initialize the Velux light."""
        self.node: Light = node
        super().__init__(node)
        self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
        self._attr_color_mode = ColorMode.BRIGHTNESS

    @property
    def brightness(self) -> int:
        """Return the current brightness."""
        return int((100 - self.node.intensity.intensity_percent) * 255 / 100)

    @property
    def is_on(self) -> bool:
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
