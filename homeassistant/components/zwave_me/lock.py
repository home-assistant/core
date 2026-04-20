"""Representation of a doorlock."""

from __future__ import annotations

from typing import Any

from zwave_me_ws import ZWaveMeData

from homeassistant.components.lock import LockEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ZWaveMePlatform
from .controller import ZWaveMeConfigEntry
from .entity import ZWaveMeEntity

DEVICE_NAME = ZWaveMePlatform.LOCK


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ZWaveMeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the lock platform."""

    @callback
    def add_new_device(new_device: ZWaveMeData) -> None:
        """Add a new device."""
        async_add_entities([ZWaveMeLock(config_entry.runtime_data, new_device)])

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"ZWAVE_ME_NEW_{DEVICE_NAME.upper()}", add_new_device
        )
    )


class ZWaveMeLock(ZWaveMeEntity, LockEntity):
    """Representation of a ZWaveMe lock."""

    @property
    def is_locked(self) -> bool:
        """Return the state of the lock."""
        return self.device.level == "close"

    def unlock(self, **kwargs: Any) -> None:
        """Send command to unlock the lock."""
        self.controller.zwave_api.send_command(self.device.id, "open")

    def lock(self, **kwargs: Any) -> None:
        """Send command to lock the lock."""
        self.controller.zwave_api.send_command(self.device.id, "close")
