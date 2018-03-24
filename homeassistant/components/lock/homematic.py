"""
Support for HomeMatic lock.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/lock.homematic/
"""
import logging
from homeassistant.components.lock import LockDevice
from homeassistant.components.homematic import HMDevice, ATTR_DISCOVER_DEVICES
from homeassistant.const import (STATE_UNKNOWN, STATE_LOCKED, STATE_UNLOCKED)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['homematic']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the HomeMatic switch platform."""
    if discovery_info is None:
        return

    devices = []
    for conf in discovery_info[ATTR_DISCOVER_DEVICES]:
        devices.append(HMLock(conf))

    add_devices(devices)


class HMLock(HMDevice, LockDevice):
    """Representation of a HomeMatic lock."""

    def _init_data_struct(self):
        """Generate the data dictionary (self._data) from metadata."""
        self._state = "STATE"
        self._data.update({self._state: STATE_UNKNOWN})

    @property
    def is_locked(self):
        """Return true if device is on."""
        try:
            return self._hm_get_state() == 0
        except TypeError:
            return False

    def lock(self, **kwargs):
        """Lock the device."""
        self._hmdevice.lock(self._channel)
        self._state = STATE_LOCKED

    def unlock(self, **kwargs):
        """Unlock the device."""
        self._hmdevice.unlock(self._channel)
        self._state = STATE_UNLOCKED
