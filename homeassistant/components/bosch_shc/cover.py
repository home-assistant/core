"""Platform for cover integration."""

from typing import Any, override

from boschshcpy import SHCShutterControl, ShutterControlService

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BoschConfigEntry
from .entity import SHCEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BoschConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SHC cover platform."""
    session = config_entry.runtime_data.session
    parent_id = config_entry.runtime_data.parent_id

    async_add_entities(
        ShutterControlCover(
            device=cover,
            parent_id=parent_id,
            entry_id=config_entry.entry_id,
        )
        for cover in session.device_helper.shutter_controls
    )


class ShutterControlCover(SHCEntity[SHCShutterControl], CoverEntity):
    """Representation of a SHC shutter control device."""

    _attr_name = None
    _attr_device_class = CoverDeviceClass.SHUTTER
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )

    @property
    @override
    def current_cover_position(self) -> int:
        """Return the current cover position."""
        return round(self._device.level * 100.0)

    @override
    def stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        self._device.stop()

    @property
    @override
    def is_closed(self) -> bool:
        """Return if the cover is closed or not."""
        return self.current_cover_position == 0

    @property
    @override
    def is_opening(self) -> bool:
        """Return if the cover is opening or not."""
        return self._device.operation_state is ShutterControlService.State.OPENING

    @property
    @override
    def is_closing(self) -> bool:
        """Return if the cover is closing or not."""
        return self._device.operation_state is ShutterControlService.State.CLOSING

    @override
    def open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        self._device.level = 1.0

    @override
    def close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        self._device.level = 0.0

    @override
    def set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position = kwargs[ATTR_POSITION]
        self._device.level = position / 100.0
