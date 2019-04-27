"""Support for Homematic locks."""
import logging

from homeassistant.components.lock import SUPPORT_OPEN, LockDevice
from homeassistant.const import STATE_UNKNOWN

from . import ATTR_DISCOVER_DEVICES, HMDevice

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Homematic lock platform."""
    if discovery_info is None:
        return

    devices = []
    for conf in discovery_info[ATTR_DISCOVER_DEVICES]:
        devices.append(HMLock(conf))

    add_entities(devices)


class HMLock(HMDevice, LockDevice):
    """Representation of a Homematic lock aka KeyMatic."""

    @property
    def is_locked(self):
        """Return true if the lock is locked."""
        return not bool(self._hm_get_state())

    def lock(self, **kwargs):
        """Lock the lock."""
        self._hmdevice.lock()

    def unlock(self, **kwargs):
        """Unlock the lock."""
        self._hmdevice.unlock()

    def open(self, **kwargs):
        """Open the door latch."""
        self._hmdevice.open()

    def _init_data_struct(self):
        """Generate the data dictionary (self._data) from metadata."""
        self._state = "STATE"
        self._data.update({self._state: STATE_UNKNOWN})

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_OPEN
