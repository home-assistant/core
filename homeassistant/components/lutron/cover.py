"""Support for Lutron shades."""

from collections.abc import Mapping
import logging
from typing import Any, override

from pylutron import Motor, Shade

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

    Adds shades and motors from the Main Repeater associated with the
    config_entry as cover entities.
    """
    entry_data = config_entry.runtime_data
    async_add_entities(
        [
            *(
                LutronCover(
                    hass, area_name, device, entry_data.client, config_entry.entry_id
                )
                for area_name, device in entry_data.covers
            ),
            *(
                LutronMotorCover(
                    hass, area_name, device, entry_data.client, config_entry.entry_id
                )
                for area_name, device in entry_data.motors
            ),
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
    _lutron_device: Shade
    _attr_name = None

    @override
    def close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        self._lutron_device.level = 0

    @override
    def open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        self._lutron_device.level = 100

    @override
    def set_cover_position(self, **kwargs: Any) -> None:
        """Move the shade to a specific position."""
        if ATTR_POSITION in kwargs:
            position = kwargs[ATTR_POSITION]
            self._lutron_device.level = position

    @override
    def _request_state(self) -> None:
        """Request the state from the device."""
        _ = self._lutron_device.level

    @override
    def _update_attrs(self) -> None:
        """Update the state attributes."""
        level = self._lutron_device.last_level()
        self._attr_is_closed = level < 1
        self._attr_current_cover_position = int(level)
        _LOGGER.debug("Lutron ID: %d updated to %f", self._lutron_device.id, level)

    @property
    @override
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes."""
        return {"lutron_integration_id": self._lutron_device.id}


class LutronMotorCover(LutronDevice, CoverEntity):
    """Representation of a Lutron MOTOR output (drapery / screen motor module).

    MOTOR outputs honor only the raise / lower / stop actions of the OUTPUT
    command; the repeater ignores "set level" for them and pylutron >= 0.4.2
    refuses it, so no position control is offered. The repeater still reports
    the position while the motor travels, which drives is_closed.
    """

    _attr_supported_features = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )
    # Motion is fire-and-forget: keep both open and close buttons usable even
    # while the last reported level says the screen is already there.
    _attr_assumed_state = True
    _lutron_device: Motor
    _attr_name = None

    @override
    def open_cover(self, **kwargs: Any) -> None:
        """Raise the motor until it reaches its limit."""
        self._lutron_device.start_raise()

    @override
    def close_cover(self, **kwargs: Any) -> None:
        """Lower the motor until it reaches its limit."""
        self._lutron_device.start_lower()

    @override
    def stop_cover(self, **kwargs: Any) -> None:
        """Stop the motor."""
        self._lutron_device.stop()

    @override
    def _request_state(self) -> None:
        """Request the state from the device."""
        _ = self._lutron_device.level

    @override
    def _update_attrs(self) -> None:
        """Update the state attributes."""
        level = self._lutron_device.last_level()
        self._attr_is_closed = level < 1
        self._attr_current_cover_position = int(level)
        _LOGGER.debug("Lutron ID: %d updated to %f", self._lutron_device.id, level)

    @property
    @override
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes."""
        return {"lutron_integration_id": self._lutron_device.id}
