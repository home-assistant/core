"""Support for Lutron shades."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from pylutron import Output

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
        [
            LutronCover(area_name, device, entry_data.client)
            for area_name, device in entry_data.covers
        ],
        True,
    )


class LutronCover(LutronDevice, CoverEntity):
    """Representation of a Lutron shade."""

    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.SET_POSITION
    )
    _lutron_device: Output

    @property
    def is_closed(self) -> bool:
        """Return if the cover is closed."""
        return self._lutron_device.last_level() < 1

    @property
    def current_cover_position(self) -> int:
        """Return the current position of cover."""
        return self._lutron_device.last_level()

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

    def update(self) -> None:
        """Call when forcing a refresh of the device."""
        # Reading the property (rather than last_level()) fetches value
        level = self._lutron_device.level
        _LOGGER.debug("Lutron ID: %d updated to %f", self._lutron_device.id, level)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes."""
        return {"lutron_integration_id": self._lutron_device.id}
