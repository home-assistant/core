"""Support for Nanoleaf sensor."""
from __future__ import annotations

import asyncio
from asyncio.tasks import Task
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .aionanoleaf import Nanoleaf, Panel
from .aionanoleaf.layout import (
    CANVAS_CONTROL_SQUARE_MASTER,
    CANVAS_CONTROL_SQUARE_PASSIVE,
    CANVAS_SQUARE,
    ELEMENTS_HEXAGONS,
    ELEMENTS_HEXAGONS_CORNER,
    LIGHT_PANELS_RHYTHM,
    LIGHT_PANELS_TRIANGLE,
    SHAPES_CONTROLLER,
    SHAPES_HEXAGON,
    SHAPES_MINI_TRIANGLE,
    SHAPES_TRIANGLE,
    UNKNOWN_SHAPE,
)
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Nanoleaf sensor."""
    nanoleaf: Nanoleaf = hass.data[DOMAIN]["device"][entry.entry_id]
    async_add_entities(
        [NanoleafPanelTouchStrength(nanoleaf, panel) for panel in nanoleaf.panels]
    )


class NanoleafPanelTouchStrength(SensorEntity):
    """Representation of a Nanoleaf panel touch strength sensor entity."""

    def __init__(self, nanoleaf: Nanoleaf, panel: Panel) -> None:
        """Initialize an Nanoleaf sensor."""
        self._nanoleaf = nanoleaf
        self._panel = panel
        self._attr_unique_id = (
            f"{self._nanoleaf.serial_no}_{self._panel.id}_touch_strength"
        )
        self._attr_name = f"{self._nanoleaf.name} {self._panel.shape.name} {self._panel.id} Touch Strength"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{self._nanoleaf.serial_no}_{self._panel.id}")},
            via_device=(DOMAIN, self._nanoleaf.serial_no),
            name=f"{self._nanoleaf.name} {self._panel.shape.name} {self._panel.id}",
            manufacturer=self._nanoleaf.manufacturer,
            model=self._panel.shape.name,
            sw_version=self._nanoleaf.firmware_version,
        )
        self._attr_should_poll = False
        self._attr_native_value = 0
        self._reset_task: Task | None = None

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend, if any."""
        return {
            LIGHT_PANELS_TRIANGLE: "mdi:triangle-outline",
            LIGHT_PANELS_RHYTHM: "mdi:music",
            CANVAS_SQUARE: "mdi:square-outline",
            CANVAS_CONTROL_SQUARE_MASTER: "mdi:border-outside",
            CANVAS_CONTROL_SQUARE_PASSIVE: "mdi:square-outline",
            SHAPES_HEXAGON: "mdi:hexagon-outline",
            SHAPES_TRIANGLE: "mdi:triangle-outline",
            SHAPES_MINI_TRIANGLE: "mdi:triangle-outline",
            SHAPES_CONTROLLER: "mdi:cellphone-wireless",
            ELEMENTS_HEXAGONS: "mdi:hexagon-outline",
            ELEMENTS_HEXAGONS_CORNER: "mdi:hexagon-outline",
            UNKNOWN_SHAPE: "mdi:help-circle-outline",
        }[self._panel.shape]

    async def async_set_state(self, value: int) -> None:
        """Set the entity state."""
        self._attr_native_value = value
        self.async_write_ha_state()
        if self._reset_task is not None and not self._reset_task.done():
            self._reset_task.cancel()
        self._reset_task = asyncio.create_task(self.reset_after_timeout())

    async def async_added_to_hass(self) -> None:
        """Handle entity being added to Home Assistant."""
        await super().async_added_to_hass()
        self.hass.data[DOMAIN]["panel_strength_entity"][self._nanoleaf.serial_no][
            self._panel.id
        ] = self

    async def reset_after_timeout(self) -> None:
        """Reset entity state after timeout."""
        # Average time between touch events is 0.125 seconds
        # Reset strength to 0 if no touch is detected for 0.25 seconds
        try:
            await asyncio.sleep(0.25)
        except asyncio.CancelledError:
            return
        self._attr_native_value = 0
        self.async_write_ha_state()
