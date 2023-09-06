"""Support for Bond covers."""
from __future__ import annotations

from typing import Any

from bond_async import Action, BPUPSubscriptions, DeviceType

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import BondEntity
from .models import BondData
from .utils import BondDevice, BondHub


def _bond_to_hass_position(bond_position: int) -> int:
    """Convert bond 0-open 100-closed to hass 0-closed 100-open."""
    return abs(bond_position - 100)


def _hass_to_bond_position(hass_position: int) -> int:
    """Convert hass 0-closed 100-open to bond 0-open 100-closed."""
    return 100 - hass_position


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bond cover devices."""
    data: BondData = hass.data[DOMAIN][entry.entry_id]
    hub = data.hub
    bpup_subs = data.bpup_subs

    async_add_entities(
        BondCover(hub, device, bpup_subs)
        for device in hub.devices
        if device.type == DeviceType.MOTORIZED_SHADES
    )


class BondCover(BondEntity, CoverEntity):
    """Representation of a Bond cover."""

    _attr_device_class = CoverDeviceClass.SHADE

    def __init__(
        self, hub: BondHub, device: BondDevice, bpup_subs: BPUPSubscriptions
    ) -> None:
        """Create HA entity representing Bond cover."""
        super().__init__(hub, device, bpup_subs)
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
        await self._hub.bond.action(
            self._device.device_id,
            Action.set_position(_hass_to_bond_position(kwargs[ATTR_POSITION])),
        )

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self._hub.bond.action(self._device.device_id, Action.open())

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        await self._hub.bond.action(self._device.device_id, Action.close())

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Hold cover."""
        await self._hub.bond.action(self._device.device_id, Action.hold())

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the cover tilt."""
        await self._hub.bond.action(self._device.device_id, Action.tilt_open())

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the cover tilt."""
        await self._hub.bond.action(self._device.device_id, Action.tilt_close())

    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self._hub.bond.action(self._device.device_id, Action.hold())
