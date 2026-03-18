"""Support for locks on Ubiquiti's UniFi Protect NVR."""

from __future__ import annotations

import logging
from typing import Any, cast

from uiprotect.data import (
    Doorlock,
    LockStatusType,
    ModelType,
    ProtectAdoptableDeviceModel,
)

from homeassistant.components.lock import LockEntity, LockEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .data import ProtectDeviceType, UFPConfigEntry
from .entity import ProtectDeviceEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UFPConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up locks on a UniFi Protect NVR."""
    data = entry.runtime_data

    @callback
    def _add_new_device(device: ProtectAdoptableDeviceModel) -> None:
        if isinstance(device, Doorlock):
            async_add_entities([ProtectLock(data, device)])

    data.async_subscribe_adopt(_add_new_device)

    async_add_entities(
        ProtectLock(
            data, cast(Doorlock, device), LockEntityDescription(key="lock", name="Lock")
        )
        for device in data.get_by_types({ModelType.DOORLOCK})
    )


class ProtectLock(ProtectDeviceEntity, LockEntity):
    """A Ubiquiti UniFi Protect Speaker."""

    device: Doorlock
    entity_description: LockEntityDescription
    _state_attrs = (
        "_attr_available",
        "_attr_is_locked",
        "_attr_is_locking",
        "_attr_is_unlocking",
        "_attr_is_jammed",
    )

    @callback
    def _async_update_device_from_protect(self, device: ProtectDeviceType) -> None:
        super()._async_update_device_from_protect(device)
        lock_status = self.device.lock_status

        self._attr_is_locked = False
        self._attr_is_locking = False
        self._attr_is_unlocking = False
        self._attr_is_jammed = False
        if lock_status is LockStatusType.CLOSED:
            self._attr_is_locked = True
        elif lock_status is LockStatusType.CLOSING:
            self._attr_is_locking = True
        elif lock_status is LockStatusType.OPENING:
            self._attr_is_unlocking = True
        elif lock_status in (
            LockStatusType.FAILED_WHILE_CLOSING,
            LockStatusType.FAILED_WHILE_OPENING,
            LockStatusType.JAMMED_WHILE_CLOSING,
            LockStatusType.JAMMED_WHILE_OPENING,
        ):
            self._attr_is_jammed = True
        # lock is not fully initialized yet
        elif lock_status != LockStatusType.OPEN:
            self._attr_available = False

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the lock."""
        _LOGGER.debug("Unlocking %s", self.device.display_name)
        return await self.device.open_lock()

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the lock."""
        _LOGGER.debug("Locking %s", self.device.display_name)
        return await self.device.close_lock()
