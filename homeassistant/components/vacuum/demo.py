"""
Demo platform for the vacuum component.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/demo/
"""
import logging

from homeassistant.const import ATTR_COMMAND
from homeassistant.components.vacuum import (
    DEFAULT_ICON, SUPPORT_BATTERY, SUPPORT_FAN_SPEED, SUPPORT_LOCATE,
    SUPPORT_PAUSE, SUPPORT_RETURN_HOME, SUPPORT_SEND_COMMAND, SUPPORT_STATUS,
    SUPPORT_STOP, SUPPORT_TURN_OFF, SUPPORT_TURN_ON, VacuumDevice)

_LOGGER = logging.getLogger(__name__)

SUPPORT_MINIMAL_SERVICES = SUPPORT_TURN_ON | SUPPORT_TURN_OFF

SUPPORT_BASIC_SERVICES = SUPPORT_TURN_ON | SUPPORT_TURN_OFF | \
                         SUPPORT_STATUS | SUPPORT_BATTERY

SUPPORT_MOST_SERVICES = SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_STOP | \
                        SUPPORT_RETURN_HOME | SUPPORT_STATUS | \
                        SUPPORT_BATTERY
SUPPORT_ALL_SERVICES = SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_PAUSE | \
                       SUPPORT_STOP | SUPPORT_RETURN_HOME | \
                       SUPPORT_FAN_SPEED | SUPPORT_SEND_COMMAND | \
                       SUPPORT_LOCATE | SUPPORT_STATUS | SUPPORT_BATTERY

FAN_SPEEDS = ['min', 'medium', 'high', 'max']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Demo vacuums."""
    add_devices([
        DemoVacuum('0_Ground floor', SUPPORT_ALL_SERVICES),
        DemoVacuum('1_First floor', SUPPORT_MOST_SERVICES),
        DemoVacuum('2_Second floor', SUPPORT_BASIC_SERVICES),
        DemoVacuum('3_Third floor', SUPPORT_MINIMAL_SERVICES),
    ])


class DemoVacuum(VacuumDevice):
    """Representation of a demo vacuum."""

    # pylint: disable=no-self-use
    def __init__(self, name, supported_features=None):
        """Initialize the vacuum."""
        self._name = name
        self._supported_features = supported_features
        self._state = False
        self._status = 'Charging'
        self._fan_speed = FAN_SPEEDS[1]
        self._cleaned_area = 0
        self._battery_level = 100
        _LOGGER.info("Vacuum '%s' supports: status? %s, battery? %s, "
                     "fan speed? %s, stop? %s, pause? %s, locate? %s, "
                     "return home? %s, send command? %s", self._name,
                     self.supported_features & SUPPORT_STATUS != 0,
                     self.supported_features & SUPPORT_BATTERY != 0,
                     self.supported_features & SUPPORT_FAN_SPEED != 0,
                     self.supported_features & SUPPORT_STOP != 0,
                     self.supported_features & SUPPORT_PAUSE != 0,
                     self.supported_features & SUPPORT_LOCATE != 0,
                     self.supported_features & SUPPORT_RETURN_HOME != 0,
                     self.supported_features & SUPPORT_SEND_COMMAND != 0)

    @property
    def name(self):
        """Return the name of the vacuum."""
        return self._name

    @property
    def icon(self):
        """Return the icon for the vacuum."""
        return DEFAULT_ICON

    @property
    def should_poll(self):
        """No polling needed for a demo vacuum."""
        return False

    @property
    def is_on(self):
        """Return true if vacuum is on."""
        return self._state

    @property
    def status(self):
        """Return the status of the vacuum."""
        if self.supported_features & SUPPORT_STATUS != 0:
            return self._status

    @property
    def fan_speed(self):
        """Return the status of the vacuum."""
        if self.supported_features & SUPPORT_FAN_SPEED != 0:
            return self._fan_speed

    @property
    def fan_speed_list(self):
        """Return the status of the vacuum."""
        if self.supported_features & SUPPORT_FAN_SPEED != 0:
            return FAN_SPEEDS

    @property
    def battery_level(self):
        """Return the status of the vacuum."""
        if self.supported_features & SUPPORT_BATTERY != 0:
            return max(0, min(100, self._battery_level))

    @property
    def device_state_attributes(self):
        """Return device state attributes."""
        return {'cleaned_area': round(self._cleaned_area, 2)}

    def turn_on(self, **kwargs):
        """Turn the vacuum on."""
        if self.supported_features & SUPPORT_TURN_ON != 0:
            self._state = True
            self._cleaned_area += 5.32
            self._battery_level -= 2
            self._status = 'Cleaning'
            self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the vacuum off."""
        if self.supported_features & SUPPORT_TURN_OFF != 0:
            self._state = False
            self._status = 'Charging'
            self.schedule_update_ha_state()

    def stop(self, **kwargs):
        """Turn the vacuum off."""
        if self.supported_features & SUPPORT_STOP != 0:
            self._state = False
            self._status = 'Stopping the current task'
            self.schedule_update_ha_state()

    def locate(self, **kwargs):
        """Turn the vacuum off."""
        if self.supported_features & SUPPORT_LOCATE != 0:
            self._status = "Hi, I'm over here!"
            self.schedule_update_ha_state()

    def start_pause(self, **kwargs):
        """Start, pause or resume the cleaning task."""
        if self.supported_features & SUPPORT_PAUSE != 0:
            self._state = not self._state
            if self._state:
                self._status = 'Resuming the current task'
                self._cleaned_area += 1.32
                self._battery_level -= 1
            else:
                self._status = 'Pausing the current task'
            self.schedule_update_ha_state()

    def set_fan_speed(self, fan_speed, **kwargs):
        """Tell the vacuum to return to its dock."""
        if self.supported_features & SUPPORT_FAN_SPEED != 0 \
                and fan_speed in self.fan_speed_list:
            self._fan_speed = fan_speed
            self.schedule_update_ha_state()

    def return_to_base(self, **kwargs):
        """Tell the vacuum to return to its dock."""
        if self.supported_features & SUPPORT_RETURN_HOME != 0:
            self._state = False
            self._status = 'Returning home...'
            self._battery_level += 5
            self.schedule_update_ha_state()

    def send_command(self, command, params=None, **kwargs):
        """Send a command to the vacuum."""
        if self.supported_features & SUPPORT_SEND_COMMAND != 0:
            command = kwargs[ATTR_COMMAND]
            self._status = "Executing %s(%s)" % (command, params)
            self._state = True
            self.schedule_update_ha_state()

    @property
    def supported_features(self):
        """Flag supported features."""
        if self._supported_features is not None:
            return self._supported_features
        return super().supported_features
