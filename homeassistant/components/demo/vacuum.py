"""Demo platform for the vacuum component."""
import logging

from homeassistant.components.vacuum import (
    ATTR_CLEANED_AREA, STATE_CLEANING, STATE_DOCKED, STATE_IDLE, STATE_PAUSED,
    STATE_RETURNING, SUPPORT_BATTERY, SUPPORT_CLEAN_SPOT, SUPPORT_FAN_SPEED,
    SUPPORT_LOCATE, SUPPORT_PAUSE, SUPPORT_RETURN_HOME, SUPPORT_SEND_COMMAND,
    SUPPORT_START, SUPPORT_STATE, SUPPORT_STATUS, SUPPORT_STOP,
    SUPPORT_TURN_OFF, SUPPORT_TURN_ON, StateVacuumDevice, VacuumDevice)

_LOGGER = logging.getLogger(__name__)

SUPPORT_MINIMAL_SERVICES = SUPPORT_TURN_ON | SUPPORT_TURN_OFF

SUPPORT_BASIC_SERVICES = SUPPORT_TURN_ON | SUPPORT_TURN_OFF | \
                         SUPPORT_STATUS | SUPPORT_BATTERY

SUPPORT_MOST_SERVICES = SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_STOP | \
                        SUPPORT_RETURN_HOME | SUPPORT_STATUS | SUPPORT_BATTERY

SUPPORT_ALL_SERVICES = SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_PAUSE | \
                       SUPPORT_STOP | SUPPORT_RETURN_HOME | \
                       SUPPORT_FAN_SPEED | SUPPORT_SEND_COMMAND | \
                       SUPPORT_LOCATE | SUPPORT_STATUS | SUPPORT_BATTERY | \
                       SUPPORT_CLEAN_SPOT

SUPPORT_STATE_SERVICES = SUPPORT_STATE | SUPPORT_PAUSE | SUPPORT_STOP | \
                         SUPPORT_RETURN_HOME | SUPPORT_FAN_SPEED | \
                         SUPPORT_BATTERY | SUPPORT_CLEAN_SPOT | SUPPORT_START

FAN_SPEEDS = ['min', 'medium', 'high', 'max']
DEMO_VACUUM_COMPLETE = '0_Ground_floor'
DEMO_VACUUM_MOST = '1_First_floor'
DEMO_VACUUM_BASIC = '2_Second_floor'
DEMO_VACUUM_MINIMAL = '3_Third_floor'
DEMO_VACUUM_NONE = '4_Fourth_floor'
DEMO_VACUUM_STATE = '5_Fifth_floor'


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Demo vacuums."""
    add_entities([
        DemoVacuum(DEMO_VACUUM_COMPLETE, SUPPORT_ALL_SERVICES),
        DemoVacuum(DEMO_VACUUM_MOST, SUPPORT_MOST_SERVICES),
        DemoVacuum(DEMO_VACUUM_BASIC, SUPPORT_BASIC_SERVICES),
        DemoVacuum(DEMO_VACUUM_MINIMAL, SUPPORT_MINIMAL_SERVICES),
        DemoVacuum(DEMO_VACUUM_NONE, 0),
        StateDemoVacuum(DEMO_VACUUM_STATE),
    ])


class DemoVacuum(VacuumDevice):
    """Representation of a demo vacuum."""

    def __init__(self, name, supported_features):
        """Initialize the vacuum."""
        self._name = name
        self._supported_features = supported_features
        self._state = False
        self._status = 'Charging'
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
    def is_on(self):
        """Return true if vacuum is on."""
        return self._state

    @property
    def status(self):
        """Return the status of the vacuum."""
        if self.supported_features & SUPPORT_STATUS == 0:
            return

        return self._status

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

    def turn_on(self, **kwargs):
        """Turn the vacuum on."""
        if self.supported_features & SUPPORT_TURN_ON == 0:
            return

        self._state = True
        self._cleaned_area += 5.32
        self._battery_level -= 2
        self._status = 'Cleaning'
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the vacuum off."""
        if self.supported_features & SUPPORT_TURN_OFF == 0:
            return

        self._state = False
        self._status = 'Charging'
        self.schedule_update_ha_state()

    def stop(self, **kwargs):
        """Stop the vacuum."""
        if self.supported_features & SUPPORT_STOP == 0:
            return

        self._state = False
        self._status = 'Stopping the current task'
        self.schedule_update_ha_state()

    def clean_spot(self, **kwargs):
        """Perform a spot clean-up."""
        if self.supported_features & SUPPORT_CLEAN_SPOT == 0:
            return

        self._state = True
        self._cleaned_area += 1.32
        self._battery_level -= 1
        self._status = "Cleaning spot"
        self.schedule_update_ha_state()

    def locate(self, **kwargs):
        """Locate the vacuum (usually by playing a song)."""
        if self.supported_features & SUPPORT_LOCATE == 0:
            return

        self._status = "Hi, I'm over here!"
        self.schedule_update_ha_state()

    def start_pause(self, **kwargs):
        """Start, pause or resume the cleaning task."""
        if self.supported_features & SUPPORT_PAUSE == 0:
            return

        self._state = not self._state
        if self._state:
            self._status = 'Resuming the current task'
            self._cleaned_area += 1.32
            self._battery_level -= 1
        else:
            self._status = 'Pausing the current task'
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

        self._state = False
        self._status = 'Returning home...'
        self._battery_level += 5
        self.schedule_update_ha_state()

    def send_command(self, command, params=None, **kwargs):
        """Send a command to the vacuum."""
        if self.supported_features & SUPPORT_SEND_COMMAND == 0:
            return

        self._status = 'Executing {}({})'.format(command, params)
        self._state = True
        self.schedule_update_ha_state()


class StateDemoVacuum(StateVacuumDevice):
    """Representation of a demo vacuum supporting states."""

    def __init__(self, name):
        """Initialize the vacuum."""
        self._name = name
        self._supported_features = SUPPORT_STATE_SERVICES
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
    def supported_features(self):
        """Flag supported features."""
        return self._supported_features

    @property
    def state(self):
        """Return the current state of the vacuum."""
        return self._state

    @property
    def battery_level(self):
        """Return the current battery level of the vacuum."""
        if self.supported_features & SUPPORT_BATTERY == 0:
            return

        return max(0, min(100, self._battery_level))

    @property
    def fan_speed(self):
        """Return the current fan speed of the vacuum."""
        if self.supported_features & SUPPORT_FAN_SPEED == 0:
            return

        return self._fan_speed

    @property
    def fan_speed_list(self):
        """Return the list of supported fan speeds."""
        if self.supported_features & SUPPORT_FAN_SPEED == 0:
            return
        return FAN_SPEEDS

    @property
    def device_state_attributes(self):
        """Return device state attributes."""
        return {ATTR_CLEANED_AREA: round(self._cleaned_area, 2)}

    def start(self):
        """Start or resume the cleaning task."""
        if self.supported_features & SUPPORT_START == 0:
            return

        if self._state != STATE_CLEANING:
            self._state = STATE_CLEANING
            self._cleaned_area += 1.32
            self._battery_level -= 1
            self.schedule_update_ha_state()

    def pause(self):
        """Pause the cleaning task."""
        if self.supported_features & SUPPORT_PAUSE == 0:
            return

        if self._state == STATE_CLEANING:
            self._state = STATE_PAUSED
            self.schedule_update_ha_state()

    def stop(self, **kwargs):
        """Stop the cleaning task, do not return to dock."""
        if self.supported_features & SUPPORT_STOP == 0:
            return

        self._state = STATE_IDLE
        self.schedule_update_ha_state()

    def return_to_base(self, **kwargs):
        """Return dock to charging base."""
        if self.supported_features & SUPPORT_RETURN_HOME == 0:
            return

        self._state = STATE_RETURNING
        self.schedule_update_ha_state()

        self.hass.loop.call_later(30, self.__set_state_to_dock)

    def clean_spot(self, **kwargs):
        """Perform a spot clean-up."""
        if self.supported_features & SUPPORT_CLEAN_SPOT == 0:
            return

        self._state = STATE_CLEANING
        self._cleaned_area += 1.32
        self._battery_level -= 1
        self.schedule_update_ha_state()

    def set_fan_speed(self, fan_speed, **kwargs):
        """Set the vacuum's fan speed."""
        if self.supported_features & SUPPORT_FAN_SPEED == 0:
            return

        if fan_speed in self.fan_speed_list:
            self._fan_speed = fan_speed
            self.schedule_update_ha_state()

    def __set_state_to_dock(self):
        self._state = STATE_DOCKED
        self.schedule_update_ha_state()
