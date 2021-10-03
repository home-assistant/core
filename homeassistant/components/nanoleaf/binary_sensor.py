"""Support for Nanoleaf binary sensor."""
from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
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
    """Set up the Nanoleaf binary sensor."""
    nanoleaf: Nanoleaf = hass.data[DOMAIN]["device"][entry.entry_id]
    async_add_entities(
        [NanoleafPanelTouch(nanoleaf, panel) for panel in nanoleaf.panels]
    )
    async_add_entities(
        [NanoleafPanelHover(nanoleaf, panel) for panel in nanoleaf.panels]
    )


class NanoleafPanelBinarySensorEntity(BinarySensorEntity):
    """Representation of a Nanoleaf panel binary sensor entity."""

    def __init__(self, nanoleaf: Nanoleaf, panel: Panel) -> None:
        """Initialize an Nanoleaf binary sensor."""
        self._nanoleaf = nanoleaf
        self._panel = panel
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{self._nanoleaf.serial_no}_{self._panel.id}")},
            via_device=(DOMAIN, self._nanoleaf.serial_no),
            name=f"{self._nanoleaf.name} {self._panel.shape.name} {self._panel.id}",
            manufacturer=self._nanoleaf.manufacturer,
            model=self._panel.shape.name,
            sw_version=self._nanoleaf.firmware_version,
        )
        self._attr_is_on = False

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend, if any."""
        if self._panel.shape == SHAPES_CONTROLLER:
            return "mdi:cellphone-wireless"
        if self._panel.shape == LIGHT_PANELS_RHYTHM:
            return "mdi:music"
        icon = {
            LIGHT_PANELS_TRIANGLE: "mdi:triangle",
            CANVAS_SQUARE: "mdi:square",
            CANVAS_CONTROL_SQUARE_MASTER: "mdi:square",
            CANVAS_CONTROL_SQUARE_PASSIVE: "mdi:square",
            SHAPES_HEXAGON: "mdi:hexagon",
            SHAPES_TRIANGLE: "mdi:triangle",
            SHAPES_MINI_TRIANGLE: "mdi:triangle",
            ELEMENTS_HEXAGONS: "mdi:hexagon",
            ELEMENTS_HEXAGONS_CORNER: "mdi:hexagon",
            UNKNOWN_SHAPE: "mdi:help-circle",
        }[self._panel.shape]
        if self.is_on:
            return icon
        return f"{icon}-outline"

    async def async_set_state(self, value: bool) -> None:
        """Set the entity state."""
        self._attr_is_on = value
        self.async_write_ha_state()


class NanoleafPanelTouch(NanoleafPanelBinarySensorEntity):
    """Representation of a Nanoleaf panel touch binary sensor entity."""

    def __init__(self, nanoleaf: Nanoleaf, panel: Panel) -> None:
        """Initialize an Nanoleaf binary sensor."""
        super().__init__(nanoleaf, panel)
        self._attr_unique_id = f"{self._nanoleaf.serial_no}_{self._panel.id}_touch"
        self._attr_name = (
            f"{self._nanoleaf.name} {self._panel.shape.name} {self._panel.id} Touch"
        )

    async def async_added_to_hass(self) -> None:
        """Handle entity being added to Home Assistant."""
        await super().async_added_to_hass()
        self.hass.data[DOMAIN]["panel_touch_entity"][self._nanoleaf.serial_no][
            self._panel.id
        ] = self


class NanoleafPanelHover(NanoleafPanelBinarySensorEntity):
    """Representation of a Nanoleaf panel touch binary sensor entity."""

    def __init__(self, nanoleaf: Nanoleaf, panel: Panel) -> None:
        """Initialize an Nanoleaf binary sensor."""
        super().__init__(nanoleaf, panel)
        self._attr_unique_id = f"{self._nanoleaf.serial_no}_{self._panel.id}_hover"
        self._attr_name = (
            f"{self._nanoleaf.name} {self._panel.shape.name} {self._panel.id} Hover"
        )

    async def async_added_to_hass(self) -> None:
        """Handle entity being added to Home Assistant."""
        await super().async_added_to_hass()
        self.hass.data[DOMAIN]["panel_hover_entity"][self._nanoleaf.serial_no][
            self._panel.id
        ] = self
