"""Support for Bond covers."""
from __future__ import annotations

from typing import Any

from bond_api import Action, BPUPSubscriptions, DeviceType

from homeassistant.components.cover import (
    DEVICE_CLASS_SHADE,
    SUPPORT_CLOSE,
    SUPPORT_CLOSE_TILT,
    SUPPORT_OPEN,
    SUPPORT_OPEN_TILT,
    SUPPORT_STOP,
    SUPPORT_STOP_TILT,
    CoverEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import BPUP_SUBS, DOMAIN, HUB
from .entity import BondEntity
from .utils import BondDevice, BondHub


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bond cover devices."""
    data = hass.data[DOMAIN][entry.entry_id]
    hub: BondHub = data[HUB]
    bpup_subs: BPUPSubscriptions = data[BPUP_SUBS]

    covers: list[Entity] = [
        BondCover(hub, device, bpup_subs)
        for device in hub.devices
        if device.type == DeviceType.MOTORIZED_SHADES
    ]

    async_add_entities(covers, True)


class BondCover(BondEntity, CoverEntity):
    """Representation of a Bond cover."""

    _attr_device_class = DEVICE_CLASS_SHADE

    def __init__(
        self, hub: BondHub, device: BondDevice, bpup_subs: BPUPSubscriptions
    ) -> None:
        """Create HA entity representing Bond cover."""
        super().__init__(hub, device, bpup_subs)
        supported_features = 0
        if self._device.supports_open():
            supported_features |= SUPPORT_OPEN
        if self._device.supports_close():
            supported_features |= SUPPORT_CLOSE
        if self._device.supports_tilt_open():
            supported_features |= SUPPORT_OPEN_TILT
        if self._device.supports_tilt_close():
            supported_features |= SUPPORT_CLOSE_TILT
        if self._device.supports_hold():
            if self._device.supports_open() or self._device.supports_close():
                supported_features |= SUPPORT_STOP
            if self._device.supports_tilt_open() or self._device.supports_tilt_close():
                supported_features |= SUPPORT_STOP_TILT
        self._attr_supported_features = supported_features

    def _apply_state(self, state: dict) -> None:
        cover_open = state.get("open")
        self._attr_is_closed = (
            True if cover_open == 0 else False if cover_open == 1 else None
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
