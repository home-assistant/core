"""Support for Yale lock."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
import logging
from typing import Any

from aiohttp import ClientResponseError
from yalexs.activity import ActivityType, ActivityTypes
from yalexs.lock import Lock, LockStatus
from yalexs.util import get_latest_activity, update_lock_detail_from_activity

from homeassistant.components.lock import ATTR_CHANGED_BY, LockEntity, LockEntityFeature
from homeassistant.const import ATTR_BATTERY_LEVEL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
import homeassistant.util.dt as dt_util

from . import YaleConfigEntry, YaleData
from .entity import YaleEntityMixin

_LOGGER = logging.getLogger(__name__)

LOCK_JAMMED_ERR = 531


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: YaleConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Yale locks."""
    data = config_entry.runtime_data
    async_add_entities(YaleLock(data, lock) for lock in data.locks)


class YaleLock(YaleEntityMixin, RestoreEntity, LockEntity):
    """Representation of an Yale lock."""

    _attr_name = None
    _lock_status: LockStatus | None = None

    def __init__(self, data: YaleData, device: Lock) -> None:
        """Initialize the lock."""
        super().__init__(data, device, "lock")
        if self._detail.unlatch_supported:
            self._attr_supported_features = LockEntityFeature.OPEN

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the device."""
        if self._data.push_updates_connected:
            await self._data.async_lock_async(self._device_id, self._hyper_bridge)
            return
        await self._call_lock_operation(self._data.async_lock)

    async def async_open(self, **kwargs: Any) -> None:
        """Open/unlatch the device."""
        if self._data.push_updates_connected:
            await self._data.async_unlatch_async(self._device_id, self._hyper_bridge)
            return
        await self._call_lock_operation(self._data.async_unlatch)

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the device."""
        if self._data.push_updates_connected:
            await self._data.async_unlock_async(self._device_id, self._hyper_bridge)
            return
        await self._call_lock_operation(self._data.async_unlock)

    async def _call_lock_operation(
        self, lock_operation: Callable[[str], Coroutine[Any, Any, list[ActivityTypes]]]
    ) -> None:
        try:
            activities = await lock_operation(self._device_id)
        except ClientResponseError as err:
            if err.status == LOCK_JAMMED_ERR:
                self._detail.lock_status = LockStatus.JAMMED
                self._detail.lock_status_datetime = dt_util.utcnow()
            else:
                raise
        else:
            for lock_activity in activities:
                update_lock_detail_from_activity(self._detail, lock_activity)

        if self._update_lock_status_from_detail():
            _LOGGER.debug(
                "async_signal_device_id_update (from lock operation): %s",
                self._device_id,
            )
            self._data.async_signal_device_id_update(self._device_id)

    def _update_lock_status_from_detail(self) -> bool:
        self._attr_available = self._detail.bridge_is_online

        if self._lock_status != self._detail.lock_status:
            self._lock_status = self._detail.lock_status
            return True
        return False

    @callback
    def _update_from_data(self) -> None:
        """Get the latest state of the sensor and update activity."""
        detail = self._detail
        if lock_activity := self._get_latest({ActivityType.LOCK_OPERATION}):
            self._attr_changed_by = lock_activity.operated_by
        lock_activity_without_operator = self._get_latest(
            {ActivityType.LOCK_OPERATION_WITHOUT_OPERATOR}
        )
        if latest_activity := get_latest_activity(
            lock_activity_without_operator, lock_activity
        ):
            if latest_activity.was_pushed:
                self._detail.set_online(True)
            update_lock_detail_from_activity(detail, latest_activity)

        if bridge_activity := self._get_latest({ActivityType.BRIDGE_OPERATION}):
            update_lock_detail_from_activity(detail, bridge_activity)

        self._update_lock_status_from_detail()
        lock_status = self._lock_status
        if lock_status is None or lock_status is LockStatus.UNKNOWN:
            self._attr_is_locked = None
        else:
            self._attr_is_locked = lock_status is LockStatus.LOCKED
        self._attr_is_jammed = lock_status is LockStatus.JAMMED
        self._attr_is_locking = lock_status is LockStatus.LOCKING
        self._attr_is_unlocking = lock_status in (
            LockStatus.UNLOCKING,
            LockStatus.UNLATCHING,
        )
        self._attr_extra_state_attributes = {ATTR_BATTERY_LEVEL: detail.battery_level}
        if keypad := detail.keypad:
            self._attr_extra_state_attributes["keypad_battery_level"] = (
                keypad.battery_level
            )

    async def async_added_to_hass(self) -> None:
        """Restore ATTR_CHANGED_BY on startup since it is likely no longer in the activity log."""
        await super().async_added_to_hass()

        if not (last_state := await self.async_get_last_state()):
            return

        if ATTR_CHANGED_BY in last_state.attributes:
            self._attr_changed_by = last_state.attributes[ATTR_CHANGED_BY]
