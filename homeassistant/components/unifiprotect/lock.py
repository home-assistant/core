"""Support for locks on Ubiquiti's UniFi Protect NVR."""
from __future__ import annotations

import logging
from typing import Any, cast

from pyunifiprotect.data import (
    Doorlock,
    LockStatusType,
    ModelType,
    ProtectAdoptableDeviceModel,
    ProtectModelWithId,
)

from homeassistant.components.lock import LockEntity, LockEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DISPATCH_ADOPT, DOMAIN
from .data import ProtectData
from .entity import ProtectDeviceEntity
from .utils import async_dispatch_id as _ufpd

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up locks on a UniFi Protect NVR."""
    data: ProtectData = hass.data[DOMAIN][entry.entry_id]

    async def _add_new_device(device: ProtectAdoptableDeviceModel) -> None:
        if isinstance(device, Doorlock):
            async_add_entities([ProtectLock(data, device)])

    entry.async_on_unload(
        async_dispatcher_connect(hass, _ufpd(entry, DISPATCH_ADOPT), _add_new_device)
    )

    entities = []
    for device in data.get_by_types({ModelType.DOORLOCK}):
        device = cast(Doorlock, device)
        entities.append(ProtectLock(data, device))

    async_add_entities(entities)


class ProtectLock(ProtectDeviceEntity, LockEntity):
    """A Ubiquiti UniFi Protect Speaker."""

    device: Doorlock
    entity_description: LockEntityDescription

    def __init__(
        self,
        data: ProtectData,
        doorlock: Doorlock,
    ) -> None:
        """Initialize an UniFi lock."""
        super().__init__(
            data,
            doorlock,
            LockEntityDescription(key="lock"),
        )

        self._attr_name = f"{self.device.display_name} Lock"

    @callback
    def _async_update_device_from_protect(self, device: ProtectModelWithId) -> None:
        super()._async_update_device_from_protect(device)

        self._attr_is_locked = False
        self._attr_is_locking = False
        self._attr_is_unlocking = False
        self._attr_is_jammed = False
        if self.device.lock_status == LockStatusType.CLOSED:
            self._attr_is_locked = True
        elif self.device.lock_status == LockStatusType.CLOSING:
            self._attr_is_locking = True
        elif self.device.lock_status == LockStatusType.OPENING:
            self._attr_is_unlocking = True
        elif self.device.lock_status in (
            LockStatusType.FAILED_WHILE_CLOSING,
            LockStatusType.FAILED_WHILE_OPENING,
            LockStatusType.JAMMED_WHILE_CLOSING,
            LockStatusType.JAMMED_WHILE_OPENING,
        ):
            self._attr_is_jammed = True
        # lock is not fully initialized yet
        elif self.device.lock_status != LockStatusType.OPEN:
            self._attr_available = False

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the lock."""
        _LOGGER.debug("Unlocking %s", self.device.display_name)
        return await self.device.open_lock()

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the lock."""
        _LOGGER.debug("Locking %s", self.device.display_name)
        return await self.device.close_lock()
