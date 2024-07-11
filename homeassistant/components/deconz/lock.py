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
from .hub import DeconzHub


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up locks for deCONZ component."""
    hub = DeconzHub.get_hub(hass, config_entry)
    hub.entities[DOMAIN] = set()

    @callback
    def async_add_lock_from_light(_: EventType, lock_id: str) -> None:
        """Add lock from deCONZ."""
        lock = hub.api.lights.locks[lock_id]
        async_add_entities([DeconzLock(lock, hub)])

    hub.register_platform_add_device_callback(
        async_add_lock_from_light,
        hub.api.lights.locks,
    )

    @callback
    def async_add_lock_from_sensor(_: EventType, lock_id: str) -> None:
        """Add lock from deCONZ."""
        lock = hub.api.sensors.door_lock[lock_id]
        async_add_entities([DeconzLock(lock, hub)])

    hub.register_platform_add_device_callback(
        async_add_lock_from_sensor,
        hub.api.sensors.door_lock,
        always_ignore_clip_sensors=True,
    )


class DeconzLock(DeconzDevice[DoorLock | Lock], LockEntity):
    """Representation of a deCONZ lock."""

    TYPE = DOMAIN

    @property
    def is_locked(self) -> bool:
        """Return true if lock is on."""
        return self._device.is_locked

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the lock."""
        if isinstance(self._device, DoorLock):
            await self.hub.api.sensors.door_lock.set_config(
                id=self._device.resource_id,
                lock=True,
            )
        else:
            await self.hub.api.lights.locks.set_state(
                id=self._device.resource_id,
                lock=True,
            )

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the lock."""
        if isinstance(self._device, DoorLock):
            await self.hub.api.sensors.door_lock.set_config(
                id=self._device.resource_id,
                lock=False,
            )
        else:
            await self.hub.api.lights.locks.set_state(
                id=self._device.resource_id,
                lock=False,
            )
