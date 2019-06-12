"""Support for Tesla door locks."""
import logging

from homeassistant.components.lock import ENTITY_ID_FORMAT, LockDevice
from homeassistant.const import STATE_LOCKED, STATE_UNLOCKED

from . import DOMAIN as TESLA_DOMAIN, TeslaDevice

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Tesla lock platform."""
    devices = [TeslaLock(device, hass.data[TESLA_DOMAIN]['controller'])
               for device in hass.data[TESLA_DOMAIN]['devices']['lock']]
    add_entities(devices, True)


class TeslaLock(TeslaDevice, LockDevice):
    """Representation of a Tesla door lock."""

    def __init__(self, tesla_device, controller):
        """Initialise of the lock."""
        self._state = None
        super().__init__(tesla_device, controller)
        self.entity_id = ENTITY_ID_FORMAT.format(self.tesla_id)

    def lock(self, **kwargs):
        """Send the lock command."""
        _LOGGER.debug("Locking doors for: %s", self._name)
        self.tesla_device.lock()

    def unlock(self, **kwargs):
        """Send the unlock command."""
        _LOGGER.debug("Unlocking doors for: %s", self._name)
        self.tesla_device.unlock()

    @property
    def is_locked(self):
        """Get whether the lock is in locked state."""
        return self._state == STATE_LOCKED

    def update(self):
        """Update state of the lock."""
        _LOGGER.debug("Updating state for: %s", self._name)
        self.tesla_device.update()
        self._state = STATE_LOCKED if self.tesla_device.is_locked() \
            else STATE_UNLOCKED
