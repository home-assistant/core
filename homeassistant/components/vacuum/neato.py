"""
Support for Neato Connected Vacuums.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/vacuum.neato/
"""
import logging
from datetime import timedelta
import requests

from homeassistant.components.vacuum import (
    StateVacuumDevice, SUPPORT_BATTERY, SUPPORT_PAUSE, SUPPORT_RETURN_HOME,
    SUPPORT_STATE, SUPPORT_STOP, SUPPORT_START, STATE_IDLE,
    STATE_PAUSED, STATE_CLEANING, STATE_DOCKED, STATE_RETURNING, STATE_ERROR,
    SUPPORT_MAP, ATTR_STATUS, ATTR_BATTERY_LEVEL, ATTR_BATTERY_ICON,
    SUPPORT_LOCATE)
from homeassistant.components.neato import (
    NEATO_ROBOTS, NEATO_LOGIN, NEATO_MAP_DATA, ACTION, ERRORS, MODE, ALERTS)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['neato']

SCAN_INTERVAL = timedelta(minutes=5)

SUPPORT_NEATO = SUPPORT_BATTERY | SUPPORT_PAUSE | SUPPORT_RETURN_HOME | \
                 SUPPORT_STOP | SUPPORT_START | \
                 SUPPORT_STATE | SUPPORT_MAP | SUPPORT_LOCATE

ATTR_CLEAN_START = 'clean_start'
ATTR_CLEAN_STOP = 'clean_stop'
ATTR_CLEAN_AREA = 'clean_area'
ATTR_CLEAN_BATTERY_START = 'battery_level_at_clean_start'
ATTR_CLEAN_BATTERY_END = 'battery_level_at_clean_end'
ATTR_CLEAN_SUSP_COUNT = 'clean_suspension_count'
ATTR_CLEAN_SUSP_TIME = 'clean_suspension_time'


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Neato vacuum."""
    dev = []
    for robot in hass.data[NEATO_ROBOTS]:
        dev.append(NeatoConnectedVacuum(hass, robot))
    _LOGGER.debug("Adding vacuums %s", dev)
    add_entities(dev, True)


class NeatoConnectedVacuum(StateVacuumDevice):
    """Representation of a Neato Connected Vacuum."""

    def __init__(self, hass, robot):
        """Initialize the Neato Connected Vacuum."""
        self.robot = robot
        self.neato = hass.data[NEATO_LOGIN]
        self._name = '{}'.format(self.robot.name)
        self._status_state = None
        self._clean_state = None
        self._state = None
        self._mapdata = hass.data[NEATO_MAP_DATA]
        self.clean_time_start = None
        self.clean_time_stop = None
        self.clean_area = None
        self.clean_battery_start = None
        self.clean_battery_end = None
        self.clean_suspension_charge_count = None
        self.clean_suspension_time = None

    def update(self):
        """Update the states of Neato Vacuums."""
        _LOGGER.debug("Running Neato Vacuums update")
        self.neato.update_robots()
        try:
            self._state = self.robot.state
        except (requests.exceptions.ConnectionError,
                requests.exceptions.HTTPError) as ex:
            _LOGGER.warning("Neato connection error: %s", ex)
            self._state = None
            return
        _LOGGER.debug('self._state=%s', self._state)
        if self._state['state'] == 1:
            if self._state['details']['isCharging']:
                self._clean_state = STATE_DOCKED
                self._status_state = 'Charging'
            elif (self._state['details']['isDocked'] and
                  not self._state['details']['isCharging']):
                self._clean_state = STATE_DOCKED
                self._status_state = 'Docked'
            else:
                self._clean_state = STATE_IDLE
                self._status_state = 'Stopped'
        elif self._state['state'] == 2:
            if ALERTS.get(self._state['error']) is None:
                self._clean_state = STATE_CLEANING
                self._status_state = (
                    MODE.get(self._state['cleaning']['mode'])
                    + ' ' + ACTION.get(self._state['action']))
            else:
                self._status_state = ALERTS.get(self._state['error'])
        elif self._state['state'] == 3:
            self._clean_state = STATE_PAUSED
            self._status_state = 'Paused'
        elif self._state['state'] == 4:
            self._clean_state = STATE_ERROR
            self._status_state = ERRORS.get(self._state['error'])

        if not self._mapdata.get(self.robot.serial, {}).get('maps', []):
            return
        self.clean_time_start = (
            (self._mapdata[self.robot.serial]['maps'][0]['start_at']
             .strip('Z'))
            .replace('T', ' '))
        self.clean_time_stop = (
            (self._mapdata[self.robot.serial]['maps'][0]['end_at'].strip('Z'))
            .replace('T', ' '))
        self.clean_area = (
            self._mapdata[self.robot.serial]['maps'][0]['cleaned_area'])
        self.clean_suspension_charge_count = (
            self._mapdata[self.robot.serial]['maps'][0]
            ['suspended_cleaning_charging_count'])
        self.clean_suspension_time = (
            self._mapdata[self.robot.serial]['maps'][0]
            ['time_in_suspended_cleaning'])
        self.clean_battery_start = (
            self._mapdata[self.robot.serial]['maps'][0]['run_charge_at_start'])
        self.clean_battery_end = (
            self._mapdata[self.robot.serial]['maps'][0]['run_charge_at_end'])

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def supported_features(self):
        """Flag vacuum cleaner robot features that are supported."""
        return SUPPORT_NEATO

    @property
    def battery_level(self):
        """Return the battery level of the vacuum cleaner."""
        return self._state['details']['charge']

    @property
    def state(self):
        """Return the status of the vacuum cleaner."""
        return self._clean_state

    @property
    def device_state_attributes(self):
        """Return the state attributes of the vacuum cleaner."""
        data = {}

        if self._status_state is not None:
            data[ATTR_STATUS] = self._status_state

        if self.battery_level is not None:
            data[ATTR_BATTERY_LEVEL] = self.battery_level
            data[ATTR_BATTERY_ICON] = self.battery_icon

        if self.clean_time_start is not None:
            data[ATTR_CLEAN_START] = self.clean_time_start
        if self.clean_time_stop is not None:
            data[ATTR_CLEAN_STOP] = self.clean_time_stop
        if self.clean_area is not None:
            data[ATTR_CLEAN_AREA] = self.clean_area
        if self.clean_suspension_charge_count is not None:
            data[ATTR_CLEAN_SUSP_COUNT] = (
                self.clean_suspension_charge_count)
        if self.clean_suspension_time is not None:
            data[ATTR_CLEAN_SUSP_TIME] = self.clean_suspension_time
        if self.clean_battery_start is not None:
            data[ATTR_CLEAN_BATTERY_START] = self.clean_battery_start
        if self.clean_battery_end is not None:
            data[ATTR_CLEAN_BATTERY_END] = self.clean_battery_end

        return data

    def start(self):
        """Start cleaning or resume cleaning."""
        if self._state['state'] == 1:
            self.robot.start_cleaning()
        elif self._state['state'] == 3:
            self.robot.resume_cleaning()

    def pause(self):
        """Pause the vacuum."""
        self.robot.pause_cleaning()

    def return_to_base(self, **kwargs):
        """Set the vacuum cleaner to return to the dock."""
        self._clean_state = STATE_RETURNING
        self.robot.send_to_base()

    def stop(self, **kwargs):
        """Stop the vacuum cleaner."""
        self.robot.stop_cleaning()

    def locate(self, **kwargs):
        """Locate the robot by making it emit a sound."""
        self.robot.locate()
