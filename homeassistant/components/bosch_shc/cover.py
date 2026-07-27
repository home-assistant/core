"""Platform for cover integration."""

from typing import TYPE_CHECKING, Any, override

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
    session = config_entry.runtime_data
    if TYPE_CHECKING:
        assert session.device_helper is not None

    shc_info = session.information
    if TYPE_CHECKING:
        assert shc_info is not None and shc_info.unique_id is not None

    async_add_entities(
        ShutterControlCover(
            device=cover,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
        )
        for cover in session.device_helper.shutter_controls
    )


class ShutterControlCover(SHCEntity, CoverEntity):
    """Representation of a SHC shutter control device."""

    _attr_name = None
    _attr_device_class = CoverDeviceClass.SHUTTER
    _device: SHCShutterControl
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
    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self._device.async_stop()

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
    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self._device.async_set_level(1.0)

    @override
    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        await self._device.async_set_level(0.0)

    @override
    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position = kwargs[ATTR_POSITION]
        await self._device.async_set_level(position / 100.0)
