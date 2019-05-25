"""Support for Neato Connected Vacuums."""
from datetime import timedelta
import logging

import requests
import voluptuous as vol

from homeassistant.components.vacuum import (
    ATTR_BATTERY_ICON, ATTR_BATTERY_LEVEL, ATTR_STATUS, DOMAIN, STATE_CLEANING,
    STATE_DOCKED, STATE_ERROR, STATE_IDLE, STATE_PAUSED, STATE_RETURNING,
    SUPPORT_BATTERY, SUPPORT_CLEAN_SPOT, SUPPORT_LOCATE, SUPPORT_MAP,
    SUPPORT_PAUSE, SUPPORT_RETURN_HOME, SUPPORT_START, SUPPORT_STATE,
    SUPPORT_STOP, StateVacuumDevice)
from homeassistant.const import ATTR_ENTITY_ID
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.service import extract_entity_ids

from . import (
    ACTION, ALERTS, ERRORS, MODE, NEATO_LOGIN, NEATO_MAP_DATA,
    NEATO_PERSISTENT_MAPS, NEATO_ROBOTS)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=5)

SUPPORT_NEATO = SUPPORT_BATTERY | SUPPORT_PAUSE | SUPPORT_RETURN_HOME | \
    SUPPORT_STOP | SUPPORT_START | SUPPORT_CLEAN_SPOT | \
    SUPPORT_STATE | SUPPORT_MAP | SUPPORT_LOCATE

ATTR_CLEAN_START = 'clean_start'
ATTR_CLEAN_STOP = 'clean_stop'
ATTR_CLEAN_AREA = 'clean_area'
ATTR_CLEAN_BATTERY_START = 'battery_level_at_clean_start'
ATTR_CLEAN_BATTERY_END = 'battery_level_at_clean_end'
ATTR_CLEAN_SUSP_COUNT = 'clean_suspension_count'
ATTR_CLEAN_SUSP_TIME = 'clean_suspension_time'

ATTR_MODE = 'mode'
ATTR_NAVIGATION = 'navigation'
ATTR_CATEGORY = 'category'
ATTR_ZONE = 'zone'

SERVICE_NEATO_CUSTOM_CLEANING = 'neato_custom_cleaning'

SERVICE_NEATO_CUSTOM_CLEANING_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Optional(ATTR_MODE, default=2): cv.positive_int,
    vol.Optional(ATTR_NAVIGATION, default=1): cv.positive_int,
    vol.Optional(ATTR_CATEGORY, default=4): cv.positive_int,
    vol.Optional(ATTR_ZONE): cv.string
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Neato vacuum."""
    dev = []
    for robot in hass.data[NEATO_ROBOTS]:
        dev.append(NeatoConnectedVacuum(hass, robot))

    if not dev:
        return

    _LOGGER.debug("Adding vacuums %s", dev)
    add_entities(dev, True)

    def neato_custom_cleaning_service(call):
        """Zone cleaning service that allows user to change options."""
        for robot in service_to_entities(call):
            if call.service == SERVICE_NEATO_CUSTOM_CLEANING:
                mode = call.data.get(ATTR_MODE)
                navigation = call.data.get(ATTR_NAVIGATION)
                category = call.data.get(ATTR_CATEGORY)
                zone = call.data.get(ATTR_ZONE)
                robot.neato_custom_cleaning(
                    mode, navigation, category, zone)

    def service_to_entities(call):
        """Return the known devices that a service call mentions."""
        entity_ids = extract_entity_ids(hass, call)
        entities = [entity for entity in dev
                    if entity.entity_id in entity_ids]
        return entities

    hass.services.register(DOMAIN, SERVICE_NEATO_CUSTOM_CLEANING,
                           neato_custom_cleaning_service,
                           schema=SERVICE_NEATO_CUSTOM_CLEANING_SCHEMA)


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
        self._available = False
        self._battery_level = None
        self._robot_serial = self.robot.serial
        self._robot_maps = hass.data[NEATO_PERSISTENT_MAPS]
        self._robot_boundaries = {}
        self._robot_has_map = self.robot.has_persistent_maps

    def update(self):
        """Update the states of Neato Vacuums."""
        _LOGGER.debug("Running Neato Vacuums update")
        self.neato.update_robots()
        try:
            self._state = self.robot.state
            self._available = True
        except (requests.exceptions.ConnectionError,
                requests.exceptions.HTTPError) as ex:
            _LOGGER.warning("Neato connection error: %s", ex)
            self._state = None
            self._available = False
            return
        _LOGGER.debug('self._state=%s', self._state)
        if 'alert' in self._state:
            robot_alert = ALERTS.get(self._state['alert'])
        else:
            robot_alert = None
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

            if robot_alert is not None:
                self._status_state = robot_alert
        elif self._state['state'] == 2:
            if robot_alert is None:
                self._clean_state = STATE_CLEANING
                self._status_state = (
                    MODE.get(self._state['cleaning']['mode'])
                    + ' ' + ACTION.get(self._state['action']))
            else:
                self._status_state = robot_alert
        elif self._state['state'] == 3:
            self._clean_state = STATE_PAUSED
            self._status_state = 'Paused'
        elif self._state['state'] == 4:
            self._clean_state = STATE_ERROR
            self._status_state = ERRORS.get(self._state['error'])

        if not self._mapdata.get(self._robot_serial, {}).get('maps', []):
            return
        self.clean_time_start = (
            (self._mapdata[self._robot_serial]['maps'][0]['start_at']
             .strip('Z'))
            .replace('T', ' '))
        self.clean_time_stop = (
            (self._mapdata[self._robot_serial]['maps'][0]['end_at'].strip('Z'))
            .replace('T', ' '))
        self.clean_area = (
            self._mapdata[self._robot_serial]['maps'][0]['cleaned_area'])
        self.clean_suspension_charge_count = (
            self._mapdata[self._robot_serial]['maps'][0]
            ['suspended_cleaning_charging_count'])
        self.clean_suspension_time = (
            self._mapdata[self._robot_serial]['maps'][0]
            ['time_in_suspended_cleaning'])
        self.clean_battery_start = (
            self._mapdata[self._robot_serial]['maps'][0]['run_charge_at_start']
        )
        self.clean_battery_end = (
            self._mapdata[self._robot_serial]['maps'][0]['run_charge_at_end'])

        self._battery_level = self._state['details']['charge']

        if self._robot_has_map:
            if self._state['availableServices']['maps'] != "basic-1":
                if self._robot_maps[self._robot_serial]:
                    robot_map_id = (
                        self._robot_maps[self._robot_serial][0]['id'])

                    self._robot_boundaries = self.robot.get_map_boundaries(
                        robot_map_id).json()

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
        return self._battery_level

    @property
    def available(self):
        """Return if the robot is available."""
        return self._available

    @property
    def state(self):
        """Return the status of the vacuum cleaner."""
        return self._clean_state

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._robot_serial

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
        if self._clean_state == STATE_CLEANING:
            self.robot.pause_cleaning()
        self._clean_state = STATE_RETURNING
        self.robot.send_to_base()

    def stop(self, **kwargs):
        """Stop the vacuum cleaner."""
        self.robot.stop_cleaning()

    def locate(self, **kwargs):
        """Locate the robot by making it emit a sound."""
        self.robot.locate()

    def clean_spot(self, **kwargs):
        """Run a spot cleaning starting from the base."""
        self.robot.start_spot_cleaning()

    def neato_custom_cleaning(self, mode, navigation, category,
                              zone=None, **kwargs):
        """Zone cleaning service call."""
        boundary_id = None
        if zone is not None:
            for boundary in self._robot_boundaries['data']['boundaries']:
                if zone in boundary['name']:
                    boundary_id = boundary['id']
            if boundary_id is None:
                _LOGGER.error(
                    "Zone '%s' was not found for the robot '%s'",
                    zone, self._name)
                return

        self._clean_state = STATE_CLEANING
        self.robot.start_cleaning(mode, navigation, category, boundary_id)
