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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LutronConfigEntry
from .entity import LutronDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LutronConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Lutron cover platform.

    Adds shades from the Main Repeater associated with the config_entry as
    cover entities.
    """
    entry_data = config_entry.runtime_data
    async_add_entities(
        [
            LutronCover(area_name, device, entry_data.client)
            for area_name, device in entry_data.covers
        ],
        True,
    )


class LutronCover(LutronDevice, CoverEntity):
    """Representation of a Lutron shade."""

    _lutron_device: Output
    _attr_name = None

    @property
    def supported_features(self) -> CoverEntityFeature:
        """Flag supported features based on output type."""
        if self._lutron_device.type == "MOTOR":
            return (
                CoverEntityFeature.OPEN
                | CoverEntityFeature.CLOSE
                | CoverEntityFeature.STOP
            )
        return (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.SET_POSITION
        )

    def close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        if self._lutron_device.type == "MOTOR":
            # Compatibility: older pylutron exposes MOTOR as Shade with
            # start_lower/start_raise/stop instead of open/close/stop.
            if hasattr(self._lutron_device, "close"):
                self._lutron_device.close()
            elif hasattr(self._lutron_device, "start_lower"):
                self._lutron_device.start_lower()
            else:
                self._lutron_device.level = 0
            return
        self._lutron_device.level = 0

    def open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        if self._lutron_device.type == "MOTOR":
            # Compatibility: older pylutron exposes MOTOR as Shade with
            # start_lower/start_raise/stop instead of open/close/stop.
            if hasattr(self._lutron_device, "open"):
                self._lutron_device.open()
            elif hasattr(self._lutron_device, "start_raise"):
                self._lutron_device.start_raise()
            else:
                self._lutron_device.level = 100
            return
        self._lutron_device.level = 100

    def stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        if self._lutron_device.type == "MOTOR":
            if hasattr(self._lutron_device, "stop"):
                self._lutron_device.stop()

    def set_cover_position(self, **kwargs: Any) -> None:
        """Move the shade to a specific position."""
        if self._lutron_device.type == "MOTOR":
            return
        if ATTR_POSITION in kwargs:
            position = kwargs[ATTR_POSITION]
            self._lutron_device.level = position

    def _request_state(self) -> None:
        """Request the state from the device."""
        _ = self._lutron_device.level

    def _update_attrs(self) -> None:
        """Update the state attributes."""
        level = self._lutron_device.last_level()
        self._attr_is_closed = level < 1
        self._attr_current_cover_position = int(level)
        _LOGGER.debug("Lutron ID: %d updated to %f", self._lutron_device.id, level)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes."""
        return {"lutron_integration_id": self._lutron_device.id}
