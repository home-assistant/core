"""Support for ThinkingCleaner."""
import time
import logging
from datetime import timedelta

import homeassistant.util as util
from homeassistant.helpers.entity import ToggleEntity

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['https://github.com/TheRealLink/pythinkingcleaner'
                '/archive/v0.0.2.zip'
                '#pythinkingcleaner==0.0.2']

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)
MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(milliseconds=100)

MIN_TIME_TO_WAIT = timedelta(seconds=5)
MIN_TIME_TO_LOCK_UPDATE = 5

SWITCH_TYPES = {
    'clean': ['Clean', None, None],
    'dock': ['Dock', None, None],
    'find': ['Find', None, None],
}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the ThinkingCleaner platform."""
    from pythinkingcleaner import Discovery

    discovery = Discovery()
    devices = discovery.discover()

    @util.Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    def update_devices():
        """Update all devices."""
        for device_object in devices:
            device_object.update()

    dev = []
    for device in devices:
        for type_name in SWITCH_TYPES.keys():
            dev.append(ThinkingCleanerSwitch(device, type_name,
                                             update_devices))

    add_devices(dev)


class ThinkingCleanerSwitch(ToggleEntity):
    """ThinkingCleaner Switch (dock, clean, find me)."""

    def __init__(self, tc_object, switch_type, update_devices):
        """Initialize the ThinkingCleaner."""
        self.type = switch_type

        self._update_devices = update_devices
        self._tc_object = tc_object
        self._state = \
            self._tc_object.is_cleaning if switch_type == 'clean' else False
        self.lock = False
        self.last_lock_time = None

    @util.Throttle(MIN_TIME_TO_WAIT)
    def lock_update(self):
        """Lock the update since TC clean takes some time to update."""
        if self.is_update_locked():
            return
        self.lock = True
        self.last_lock_time = time.time()

    def is_update_locked(self):
        """Check if the update method is locked."""
        if self.last_lock_time is None:
            return False

        if time.time() - self.last_lock_time >= MIN_TIME_TO_LOCK_UPDATE:
            self.last_lock_time = None
            return False

        return True

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._tc_object.name + ' ' + SWITCH_TYPES[self.type][0]

    @property
    def is_on(self):
        """Return true if device is on."""
        if self.type == 'clean':
            if not self.is_update_locked():
                self._update_devices()
            return self._tc_object.is_cleaning

        return False

    def turn_on(self, **kwargs):
        """Turn the device on."""
        if self.type == 'clean':
            self.lock_update()
            self._tc_object.start_cleaning()
        elif self.type == 'dock':
            self._tc_object.dock()
        elif self.type == 'find':
            self._tc_object.find_me()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        if self.type == 'clean':
            self._tc_object.stop_cleaning()
