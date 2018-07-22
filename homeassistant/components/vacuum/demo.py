"""
Demo platform for the vacuum component.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/demo/
"""
import logging

from homeassistant.components.vacuum import (
    ATTR_CLEANED_AREA, SUPPORT_BATTERY, SUPPORT_CLEAN_SPOT,
    SUPPORT_FAN_SPEED, SUPPORT_LOCATE, SUPPORT_PAUSE, SUPPORT_RETURN_HOME,
    SUPPORT_SEND_COMMAND, SUPPORT_STATE, SUPPORT_STOP, SUPPORT_START,
    STATE_CLEANING, STATE_DOCKED, STATE_PAUSED,
    STATE_IDLE, STATE_RETURNING, STATE_ERROR, VacuumDevice)

_LOGGER = logging.getLogger(__name__)

SUPPORT_MINIMAL_SERVICES = SUPPORT_START | SUPPORT_STOP

SUPPORT_BASIC_SERVICES = SUPPORT_START | SUPPORT_STOP | \
                         SUPPORT_STATE | SUPPORT_BATTERY

SUPPORT_MOST_SERVICES = SUPPORT_START | SUPPORT_STOP | \
                        SUPPORT_RETURN_HOME | SUPPORT_STATE | SUPPORT_BATTERY

SUPPORT_ALL_SERVICES = SUPPORT_START | SUPPORT_STOP | SUPPORT_PAUSE | \
                       SUPPORT_RETURN_HOME | \
                       SUPPORT_FAN_SPEED | SUPPORT_SEND_COMMAND | \
                       SUPPORT_LOCATE | SUPPORT_STATE | SUPPORT_BATTERY | \
                       SUPPORT_CLEAN_SPOT

FAN_SPEEDS = ['min', 'medium', 'high', 'max']
DEMO_VACUUM_COMPLETE = '0_Ground_floor'
DEMO_VACUUM_MOST = '1_First_floor'
DEMO_VACUUM_BASIC = '2_Second_floor'
DEMO_VACUUM_MINIMAL = '3_Third_floor'
DEMO_VACUUM_NONE = '4_Fourth_floor'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Demo vacuums."""
    add_devices([
        DemoVacuum(DEMO_VACUUM_COMPLETE, SUPPORT_ALL_SERVICES),
        DemoVacuum(DEMO_VACUUM_MOST, SUPPORT_MOST_SERVICES),
        DemoVacuum(DEMO_VACUUM_BASIC, SUPPORT_BASIC_SERVICES),
        DemoVacuum(DEMO_VACUUM_MINIMAL, SUPPORT_MINIMAL_SERVICES),
        DemoVacuum(DEMO_VACUUM_NONE, 0),
    ])


class DemoVacuum(VacuumDevice):
    """Representation of a demo vacuum."""

    def __init__(self, name, supported_features):
        """Initialize the vacuum."""
        self._name = name
        self._supported_features = supported_features
        self._state = STATE_DOCKED
        self._fan_speed = FAN_SPEEDS[1]
        self._cleaned_area = 0
        self._battery_level = 100

    @property
    def name(self):
        """Return the name of the vacuum."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed for a demo vacuum."""
        return False


    @property
    def state(self):
        """Return the status of the vacuum."""
        if self.supported_features & SUPPORT_STATE == 0:
            return

        return self._state

    @property
    def fan_speed(self):
        """Return the status of the vacuum."""
        if self.supported_features & SUPPORT_FAN_SPEED == 0:
            return

        return self._fan_speed

    @property
    def fan_speed_list(self):
        """Return the status of the vacuum."""
        assert self.supported_features & SUPPORT_FAN_SPEED != 0
        return FAN_SPEEDS

    @property
    def battery_level(self):
        """Return the status of the vacuum."""
        if self.supported_features & SUPPORT_BATTERY == 0:
            return

        return max(0, min(100, self._battery_level))

    @property
    def device_state_attributes(self):
        """Return device state attributes."""
        return {ATTR_CLEANED_AREA: round(self._cleaned_area, 2)}

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._supported_features

    def stop(self, **kwargs):
        """Stop the vacuum."""
        if self.supported_features & SUPPORT_STOP == 0:
            return

        self._state = STATE_IDLE
        self.schedule_update_ha_state()

    def clean_spot(self, **kwargs):
        """Perform a spot clean-up."""
        if self.supported_features & SUPPORT_CLEAN_SPOT == 0:
            return

        self._cleaned_area += 1.32
        self._battery_level -= 1
        self._state = STATE_CLEANING
        self.schedule_update_ha_state()

    def locate(self, **kwargs):
        """Locate the vacuum (usually by playing a song)."""
        if self.supported_features & SUPPORT_LOCATE == 0:
            return

        self.schedule_update_ha_state()

    def start_pause(self, **kwargs):
        """Start, pause or resume the cleaning task."""
        if self.supported_features & SUPPORT_PAUSE == 0:
            return

        if self._state == STATE_PAUSED:
            self._state = STATE_CLEANING
            self._cleaned_area += 1.32
            self._battery_level -= 1
        else:
            self._state = STATE_PAUSED
        self.schedule_update_ha_state()

    def set_fan_speed(self, fan_speed, **kwargs):
        """Set the vacuum's fan speed."""
        if self.supported_features & SUPPORT_FAN_SPEED == 0:
            return

        if fan_speed in self.fan_speed_list:
            self._fan_speed = fan_speed
            self.schedule_update_ha_state()

    def return_to_base(self, **kwargs):
        """Tell the vacuum to return to its dock."""
        if self.supported_features & SUPPORT_RETURN_HOME == 0:
            return

        self._state = STATE_RETURNING
        self._battery_level += 5
        self.schedule_update_ha_state()

    def send_command(self, command, params=None, **kwargs):
        """Send a command to the vacuum."""
        if self.supported_features & SUPPORT_SEND_COMMAND == 0:
            return

        self.schedule_update_ha_state()
