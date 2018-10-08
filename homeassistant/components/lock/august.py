"""
Support for August lock.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/lock.august/
"""
import logging
from datetime import timedelta

from homeassistant.components.august import DATA_AUGUST
from homeassistant.components.lock import LockDevice
from homeassistant.const import ATTR_BATTERY_LEVEL

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['august']

SCAN_INTERVAL = timedelta(seconds=5)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up August locks."""
    data = hass.data[DATA_AUGUST]
    devices = []

    for lock in data.locks:
        _LOGGER.debug("Adding lock for %s", lock.device_name)
        devices.append(AugustLock(data, lock))

    add_entities(devices, True)


class AugustLock(LockDevice):
    """Representation of an August lock."""

    def __init__(self, data, lock):
        """Initialize the lock."""
        self._data = data
        self._lock = lock
        self._lock_status = None
        self._lock_detail = None
        self._changed_by = None

    def lock(self, **kwargs):
        """Lock the device."""
        self._data.lock(self._lock.device_id)

    def unlock(self, **kwargs):
        """Unlock the device."""
        self._data.unlock(self._lock.device_id)

    def update(self):
        """Get the latest state of the sensor."""
        self._lock_status = self._data.get_lock_status(self._lock.device_id)
        self._lock_detail = self._data.get_lock_detail(self._lock.device_id)

        from august.activity import ActivityType
        activity = self._data.get_latest_device_activity(
            self._lock.device_id,
            ActivityType.LOCK_OPERATION)

        if activity is not None:
            self._changed_by = activity.operated_by

    @property
    def name(self):
        """Return the name of this device."""
        return self._lock.device_name

    @property
    def is_locked(self):
        """Return true if device is on."""
        from august.lock import LockStatus
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

        return {
            ATTR_BATTERY_LEVEL: self._lock_detail.battery_level,
        }
