"""Support for deCONZ locks."""

from __future__ import annotations

from typing import Any

from pydeconz.models.event import EventType
from pydeconz.models.light.lock import Lock
from pydeconz.models.sensor.door_lock import DoorLock

from homeassistant.components.lock import DOMAIN, LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .deconz_device import DeconzDevice
from .gateway import get_gateway_from_config_entry


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up locks for deCONZ component."""
    gateway = get_gateway_from_config_entry(hass, config_entry)
    gateway.entities[DOMAIN] = set()

    @callback
    def async_add_lock_from_light(_: EventType, lock_id: str) -> None:
        """Add lock from deCONZ."""
        lock = gateway.api.lights.locks[lock_id]
        async_add_entities([DeconzLock(lock, gateway)])

    gateway.register_platform_add_device_callback(
        async_add_lock_from_light,
        gateway.api.lights.locks,
    )

    @callback
    def async_add_lock_from_sensor(_: EventType, lock_id: str) -> None:
        """Add lock from deCONZ."""
        lock = gateway.api.sensors.door_lock[lock_id]
        async_add_entities([DeconzLock(lock, gateway)])

    gateway.register_platform_add_device_callback(
        async_add_lock_from_sensor,
        gateway.api.sensors.door_lock,
    )


class DeconzLock(DeconzDevice, LockEntity):
    """Representation of a deCONZ lock."""

    TYPE = DOMAIN
    _device: DoorLock | Lock

    @property
    def is_locked(self) -> bool:
        """Return true if lock is on."""
        return self._device.is_locked

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the lock."""
        if isinstance(self._device, DoorLock):
            await self.gateway.api.sensors.door_lock.set_config(
                id=self._device.resource_id,
                lock=True,
            )
        else:
            await self.gateway.api.lights.locks.set_state(
                id=self._device.resource_id,
                lock=True,
            )

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the lock."""
        if isinstance(self._device, DoorLock):
            await self.gateway.api.sensors.door_lock.set_config(
                id=self._device.resource_id,
                lock=False,
            )
        else:
            await self.gateway.api.lights.locks.set_state(
                id=self._device.resource_id,
                lock=False,
            )
