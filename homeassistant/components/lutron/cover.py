"""Support for Lutron shades."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from pylutron import LutronEntity, LutronEvent, Output

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN, LutronData
from .entity import LutronDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Lutron cover platform.

    Adds shades from the Main Repeater associated with the config_entry as
    cover entities.
    """
    entry_data: LutronData = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        LutronCover(area_name, device, entry_data.client)
        for area_name, device in entry_data.covers
    )


class LutronCover(LutronDevice, CoverEntity):
    """Representation of a Lutron shade."""

    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.SET_POSITION
    )
    _lutron_device: Output
    _attr_name = None

    def close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        self._lutron_device.level = 0

    def open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        self._lutron_device.level = 100

    def set_cover_position(self, **kwargs: Any) -> None:
        """Move the shade to a specific position."""
        if ATTR_POSITION in kwargs:
            position = kwargs[ATTR_POSITION]
            self._lutron_device.level = position

    def _update_callback(
        self, device: LutronEntity, context: None, event: LutronEvent, params: dict
    ) -> None:
        """Run when invoked by pylutron when the device state changes."""
        level = self._lutron_device.level
        self._attr_is_closed = level < 1
        self._attr_current_cover_position = level
        _LOGGER.debug("Lutron ID: %d updated to %f", self._lutron_device.id, level)

        super()._update_callback(device, context, event, params)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes."""
        return {"lutron_integration_id": self._lutron_device.id}
