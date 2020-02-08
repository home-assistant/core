"""Support for Tahoma lock."""
from datetime import timedelta
import logging

from homeassistant.components.lock import LockDevice
from homeassistant.const import ATTR_BATTERY_LEVEL, STATE_LOCKED, STATE_UNLOCKED

from . import DOMAIN as TAHOMA_DOMAIN, TahomaDevice

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=120)
TAHOMA_STATE_LOCKED = "locked"


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Tahoma lock."""
    if discovery_info is None:
        return
    controller = hass.data[TAHOMA_DOMAIN]["controller"]
    devices = []
    for device in hass.data[TAHOMA_DOMAIN]["devices"]["lock"]:
        devices.append(TahomaLock(device, controller))
    add_entities(devices, True)


class TahomaLock(TahomaDevice, LockDevice):
    """Representation a Tahoma lock."""

    def __init__(self, tahoma_device, controller):
        """Initialize the device."""
        super().__init__(tahoma_device, controller)
        self._lock_status = None
        self._available = False
        self._battery_level = None
        self._name = None

    def update(self):
        """Update method."""
        self.controller.get_states([self.tahoma_device])
        self._battery_level = self.tahoma_device.active_states["core:BatteryState"]
        self._name = self.tahoma_device.active_states["core:NameState"]
        if (
            self.tahoma_device.active_states.get("core:LockedUnlockedState")
            == TAHOMA_STATE_LOCKED
        ):
            self._lock_status = STATE_LOCKED
        else:
            self._lock_status = STATE_UNLOCKED
        self._available = (
            self.tahoma_device.active_states.get("core:AvailabilityState")
            == "available"
        )

    def unlock(self, **kwargs):
        """Unlock method."""
        _LOGGER.debug("Unlocking %s", self._name)
        self.apply_action("unlock")

    def lock(self, **kwargs):
        """Lock method."""
        _LOGGER.debug("Locking %s", self._name)
        self.apply_action("lock")

    @property
    def name(self):
        """Return the name of the lock."""
        return self._name

    @property
    def available(self):
        """Return True if the lock is available."""
        return self._available

    @property
    def is_locked(self):
        """Return True if the lock is locked."""
        return self._lock_status == STATE_LOCKED

    @property
    def device_state_attributes(self):
        """Return the lock state attributes."""
        attr = {
            ATTR_BATTERY_LEVEL: self._battery_level,
        }
        super_attr = super().device_state_attributes
        if super_attr is not None:
            attr.update(super_attr)
        return attr
