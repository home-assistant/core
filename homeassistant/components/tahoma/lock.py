"""Support for Tahoma lock."""
from datetime import timedelta
import logging

from homeassistant.components.lock import LockDevice
from homeassistant.const import ATTR_BATTERY_LEVEL, STATE_LOCKED, STATE_UNLOCKED

from . import DOMAIN as TAHOMA_DOMAIN, TahomaDevice

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=120)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Tahoma covers."""
    controller = hass.data[TAHOMA_DOMAIN]['controller']
    devices = []
    for device in hass.data[TAHOMA_DOMAIN]['devices']['lock']:
        devices.append(TahomaLock(device, controller))
    add_entities(devices, True)


class TahomaLock(TahomaDevice, LockDevice):

    def __init__(self, tahoma_device, controller):
        """Initialize the device."""
        super().__init__(tahoma_device, controller)
        self._state = STATE_LOCKED
        self._available = False
        self._battery_level = None
        self._name = None

    def update(self):
        """Update method."""
        self.controller.get_states([self.tahoma_device])
        self._battery_level = self.tahoma_device.active_states['core:BatteryState']
        self._name = self.tahoma_device.active_states['core:NameState']
        if self._battery_level == 'low':
            _LOGGER.warning("Lock "+self._name+" has low battery")
        if self._battery_level == 'verylow':
            _LOGGER.error("Lock " + self._name + " has very low battery")
        if self.tahoma_device.active_states.get('core:LockedUnlockedState') == 'locked':
            self._state = STATE_LOCKED
        else:
            self._state = STATE_UNLOCKED
        self._available = self.tahoma_device.active_states.get('core:AvailabilityState') == 'available'

    def open(self, **kwargs):
        pass

    def unlock(self, **kwargs):
        _LOGGER.info("unlocking ",self._name)
        self.apply_action('unlock')

    def lock(self, **kwargs):
        _LOGGER.info("locking ",self._name)
        self.apply_action('lock')

    @property
    def is_locked(self):
        return self._state == STATE_LOCKED

    @property
    def state(self):
        """Return the state."""
        print(self._state)
        return self._state

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        attr = {}
        super_attr = super().device_state_attributes
        if super_attr is not None:
            attr.update(super_attr)
        attr[ATTR_BATTERY_LEVEL] = \
            self.tahoma_device.active_states['core:BatteryState']
        attr['availability'] = \
            self.tahoma_device.active_states['core:AvailabilityState']
        attr['name'] = \
            self.tahoma_device.active_states['core:NameState']
        return attr
