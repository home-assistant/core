"""Support for Bond covers."""

from __future__ import annotations

from typing import Any

from bond_async import Action, DeviceType

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BondConfigEntry
from .entity import BondEntity
from .models import BondData
from .utils import BondDevice


def _bond_to_hass_position(bond_position: int) -> int:
    """Convert bond 0-open 100-closed to hass 0-closed 100-open."""
    return abs(bond_position - 100)


def _hass_to_bond_position(hass_position: int) -> int:
    """Convert hass 0-closed 100-open to bond 0-open 100-closed."""
    return 100 - hass_position


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BondConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bond cover devices."""
    data = entry.runtime_data
    async_add_entities(
        BondCover(data, device)
        for device in data.hub.devices
        if device.type == DeviceType.MOTORIZED_SHADES
    )


class BondCover(BondEntity, CoverEntity):
    """Representation of a Bond cover."""

    _attr_device_class = CoverDeviceClass.SHADE

    def __init__(self, data: BondData, device: BondDevice) -> None:
        """Create HA entity representing Bond cover."""
        super().__init__(data, device)
        supported_features = CoverEntityFeature(0)
        if self._device.supports_set_position():
            supported_features |= CoverEntityFeature.SET_POSITION
        if self._device.supports_open():
            supported_features |= CoverEntityFeature.OPEN
        if self._device.supports_close():
            supported_features |= CoverEntityFeature.CLOSE
        if self._device.supports_tilt_open():
            supported_features |= CoverEntityFeature.OPEN_TILT
        if self._device.supports_tilt_close():
            supported_features |= CoverEntityFeature.CLOSE_TILT
        if self._device.supports_hold():
            if self._device.supports_open() or self._device.supports_close():
                supported_features |= CoverEntityFeature.STOP
            if self._device.supports_tilt_open() or self._device.supports_tilt_close():
                supported_features |= CoverEntityFeature.STOP_TILT
        self._attr_supported_features = supported_features

    def _apply_state(self) -> None:
        state = self._device.state
        cover_open = state.get("open")
        self._attr_is_closed = None if cover_open is None else cover_open == 0
        if (bond_position := state.get("position")) is not None:
            self._attr_current_cover_position = _bond_to_hass_position(bond_position)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set the cover position."""
        await self._bond.action(
            self._device_id,
            Action.set_position(_hass_to_bond_position(kwargs[ATTR_POSITION])),
        )

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self._bond.action(self._device_id, Action.open())

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        await self._bond.action(self._device_id, Action.close())

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Hold cover."""
        await self._bond.action(self._device_id, Action.hold())

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the cover tilt."""
        await self._bond.action(self._device_id, Action.tilt_open())

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the cover tilt."""
        await self._bond.action(self._device_id, Action.tilt_close())

    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self._bond.action(self._device_id, Action.hold())
