"""Support for August lock."""
import logging
from typing import Any

from aiohttp import ClientResponseError
from yalexs.activity import SOURCE_PUBNUB, ActivityType
from yalexs.lock import LockStatus
from yalexs.util import get_latest_activity, update_lock_detail_from_activity

from homeassistant.components.lock import ATTR_CHANGED_BY, LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_BATTERY_LEVEL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
import homeassistant.util.dt as dt_util

from . import AugustData
from .const import DOMAIN
from .entity import AugustEntityMixin

_LOGGER = logging.getLogger(__name__)

LOCK_JAMMED_ERR = 531


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up August locks."""
    data: AugustData = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(AugustLock(data, lock) for lock in data.locks)


class AugustLock(AugustEntityMixin, RestoreEntity, LockEntity):
    """Representation of an August lock."""

    def __init__(self, data, device):
        """Initialize the lock."""
        super().__init__(data, device)
        self._lock_status = None
        self._attr_name = device.device_name
        self._attr_unique_id = f"{self._device_id:s}_lock"
        self._update_from_data()

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the device."""
        assert self._data.activity_stream is not None
        if self._data.activity_stream.pubnub.connected:
            await self._data.async_lock_async(self._device_id, self._hyper_bridge)
            return
        await self._call_lock_operation(self._data.async_lock)

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the device."""
        assert self._data.activity_stream is not None
        if self._data.activity_stream.pubnub.connected:
            await self._data.async_unlock_async(self._device_id, self._hyper_bridge)
            return
        await self._call_lock_operation(self._data.async_unlock)

    async def _call_lock_operation(self, lock_operation):
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

    def _update_lock_status_from_detail(self):
        self._attr_available = self._detail.bridge_is_online

        if self._lock_status != self._detail.lock_status:
            self._lock_status = self._detail.lock_status
            return True
        return False

    @callback
    def _update_from_data(self):
        """Get the latest state of the sensor and update activity."""
        activity_stream = self._data.activity_stream
        device_id = self._device_id
        if lock_activity := activity_stream.get_latest_device_activity(
            device_id,
            {ActivityType.LOCK_OPERATION},
        ):
            self._attr_changed_by = lock_activity.operated_by

        lock_activity_without_operator = activity_stream.get_latest_device_activity(
            device_id,
            {ActivityType.LOCK_OPERATION_WITHOUT_OPERATOR},
        )

        if latest_activity := get_latest_activity(
            lock_activity_without_operator, lock_activity
        ):
            if latest_activity.source == SOURCE_PUBNUB:
                # If the source is pubnub the lock must be online since its a live update
                self._detail.set_online(True)
            update_lock_detail_from_activity(self._detail, latest_activity)

        bridge_activity = self._data.activity_stream.get_latest_device_activity(
            self._device_id, {ActivityType.BRIDGE_OPERATION}
        )

        if bridge_activity is not None:
            update_lock_detail_from_activity(self._detail, bridge_activity)

        self._update_lock_status_from_detail()
        if self._lock_status is None or self._lock_status is LockStatus.UNKNOWN:
            self._attr_is_locked = None
        else:
            self._attr_is_locked = self._lock_status is LockStatus.LOCKED

        self._attr_is_jammed = self._lock_status is LockStatus.JAMMED
        self._attr_is_locking = self._lock_status is LockStatus.LOCKING
        self._attr_is_unlocking = self._lock_status is LockStatus.UNLOCKING

        self._attr_extra_state_attributes = {
            ATTR_BATTERY_LEVEL: self._detail.battery_level
        }
        if self._detail.keypad is not None:
            self._attr_extra_state_attributes[
                "keypad_battery_level"
            ] = self._detail.keypad.battery_level

    async def async_added_to_hass(self) -> None:
        """Restore ATTR_CHANGED_BY on startup since it is likely no longer in the activity log."""
        await super().async_added_to_hass()

        if not (last_state := await self.async_get_last_state()):
            return

        if ATTR_CHANGED_BY in last_state.attributes:
            self._attr_changed_by = last_state.attributes[ATTR_CHANGED_BY]
