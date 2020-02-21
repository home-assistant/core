"""Support for August lock."""
from datetime import timedelta
import logging

from august.activity import ActivityType
from august.lock import LockStatus
from august.util import update_lock_detail_from_activity

from homeassistant.components.lock import LockDevice
from homeassistant.const import ATTR_BATTERY_LEVEL
from homeassistant.util import dt

from . import DATA_AUGUST

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=5)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up August locks."""
    data = hass.data[DATA_AUGUST]
    devices = []

    for lock in data.locks:
        _LOGGER.debug("Adding lock for %s", lock.device_name)
        devices.append(AugustLock(data, lock))

    async_add_entities(devices, True)


class AugustLock(LockDevice):
    """Representation of an August lock."""

    def __init__(self, data, lock):
        """Initialize the lock."""
        self._data = data
        self._lock = lock
        self._lock_status = None
        self._lock_detail = None
        self._changed_by = None
        self._available = False

    async def async_lock(self, **kwargs):
        """Lock the device."""
        update_start_time_utc = dt.utcnow()
        lock_status = await self.hass.async_add_executor_job(
            self._data.lock, self._lock.device_id
        )
        self._update_lock_status(lock_status, update_start_time_utc)

    async def async_unlock(self, **kwargs):
        """Unlock the device."""
        update_start_time_utc = dt.utcnow()
        lock_status = await self.hass.async_add_executor_job(
            self._data.unlock, self._lock.device_id
        )
        self._update_lock_status(lock_status, update_start_time_utc)

    def _update_lock_status(self, lock_status, update_start_time_utc):
        if self._lock_status != lock_status:
            self._lock_status = lock_status
            self._data.update_lock_status(
                self._lock.device_id, lock_status, update_start_time_utc
            )
            self.schedule_update_ha_state()

    async def async_update(self):
        """Get the latest state of the sensor and update activity."""
        self._lock_detail = await self._data.async_get_lock_detail(self._lock.device_id)
        lock_activity = await self._data.async_get_latest_device_activity(
            self._lock.device_id, ActivityType.LOCK_OPERATION
        )

        if lock_activity is not None:
            self._changed_by = lock_activity.operated_by
            update_lock_detail_from_activity(self._lock_detail, lock_activity)

        self._lock_status = self._lock_detail.lock_status
        self._available = (
            self._lock_status is not None and self._lock_status != LockStatus.UNKNOWN
        )

    @property
    def name(self):
        """Return the name of this device."""
        return self._lock.device_name

    @property
    def available(self):
        """Return the availability of this sensor."""
        return self._available

    @property
    def is_locked(self):
        """Return true if device is on."""

        return self._lock_status is LockStatus.LOCKED

    @property
    def changed_by(self):
        """Last change triggered by."""
        return self._changed_by

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        if self._lock_detail is None:
            return None

        attributes = {ATTR_BATTERY_LEVEL: self._lock_detail.battery_level}

        if self._lock_detail.keypad is not None:
            attributes["keypad_battery_level"] = self._lock_detail.keypad.battery_level

        return attributes

    @property
    def unique_id(self) -> str:
        """Get the unique id of the lock."""
        return f"{self._lock.device_id:s}_lock"
