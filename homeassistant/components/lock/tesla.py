"""
Support for Tesla door locks.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/lock.tesla/
"""
import logging
from homeassistant.components.lock import ENTITY_ID_FORMAT, LockDevice
from homeassistant.const import (STATE_LOCKED, STATE_UNLOCKED)
from homeassistant.components.tesla import (
    TESLA_CONTROLLER, TESLA_DEVICES, TeslaDevice)

DEPENDENCIES = ['tesla']
_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Tesla lock platform."""
    devices = [TeslaLock(device, TESLA_CONTROLLER)
               for device in TESLA_DEVICES['lock']]
    add_devices(devices, True)


class TeslaLock(TeslaDevice, LockDevice):
    """Representation of Tesla door lock class."""

    def __init__(self, tesla_device, controller):
        """Initialisation."""
        self._state = None
        TeslaDevice.__init__(self, tesla_device, controller)
        self._name = self.tesla_device.name
        self.entity_id = ENTITY_ID_FORMAT.format(self.tesla_id)

    def lock(self, **kwargs):
        """Send the lock command."""
        _LOGGER.debug('Locking doors for:', self._name)
        self.tesla_device.lock()
        self._state = STATE_LOCKED

    def unlock(self, **kwargs):
        """Send the unlock command."""
        _LOGGER.debug('Unlocking doors for:', self._name)
        self.tesla_device.unlock()
        self._state = STATE_UNLOCKED

    @property
    def should_poll(self):
        """No polling needed for a demo lock."""
        return True

    @property
    def is_locked(self):
        """Get whether the lock is in locked state."""
        return self._state == STATE_LOCKED

    def update(self):
        """Updating state of the lock."""
        _LOGGER.debug('Updating state for:', self._name)
        self.tesla_device.update()
        self._state = STATE_LOCKED if self.tesla_device.is_locked() \
            else STATE_UNLOCKED
