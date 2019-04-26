"""Support for Netatmo Smart thermostats."""
import logging
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.climate import ClimateDevice, PLATFORM_SCHEMA
from homeassistant.components.climate.const import (
    STATE_HEAT, SUPPORT_ON_OFF, SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_OPERATION_MODE, SUPPORT_AWAY_MODE, STATE_MANUAL, STATE_AUTO,
    STATE_ECO, STATE_COOL)
from homeassistant.const import (
    STATE_OFF, TEMP_CELSIUS, ATTR_TEMPERATURE, CONF_NAME)
from homeassistant.util import Throttle

from .const import DATA_NETATMO_AUTH

_LOGGER = logging.getLogger(__name__)

CONF_HOMES = 'homes'
CONF_ROOMS = 'rooms'

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=10)

HOME_CONFIG_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
    vol.Optional(CONF_ROOMS, default=[]): vol.All(cv.ensure_list, [cv.string])
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOMES): vol.All(cv.ensure_list, [HOME_CONFIG_SCHEMA])
})

STATE_NETATMO_SCHEDULE = 'schedule'
STATE_NETATMO_HG = 'hg'
STATE_NETATMO_MAX = 'max'
STATE_NETATMO_AWAY = 'away'
STATE_NETATMO_OFF = STATE_OFF
STATE_NETATMO_MANUAL = STATE_MANUAL

DICT_NETATMO_TO_HA = {
    STATE_NETATMO_SCHEDULE: STATE_AUTO,
    STATE_NETATMO_HG: STATE_COOL,
    STATE_NETATMO_MAX: STATE_HEAT,
    STATE_NETATMO_AWAY: STATE_ECO,
    STATE_NETATMO_OFF: STATE_OFF,
    STATE_NETATMO_MANUAL: STATE_MANUAL
}

DICT_HA_TO_NETATMO = {
    STATE_AUTO: STATE_NETATMO_SCHEDULE,
    STATE_COOL: STATE_NETATMO_HG,
    STATE_HEAT: STATE_NETATMO_MAX,
    STATE_ECO: STATE_NETATMO_AWAY,
    STATE_OFF: STATE_NETATMO_OFF,
    STATE_MANUAL: STATE_NETATMO_MANUAL
}

SUPPORT_FLAGS = (SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE |
                 SUPPORT_AWAY_MODE)

NA_THERM = 'NATherm1'
NA_VALVE = 'NRV'


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the NetAtmo Thermostat."""
    import pyatmo
    homes_conf = config.get(CONF_HOMES)

    auth = hass.data[DATA_NETATMO_AUTH]

    try:
        home_data = HomeData(auth)
    except pyatmo.NoDevice:
        return

    homes = []
    rooms = {}
    if homes_conf is not None:
        for home_conf in homes_conf:
            home = home_conf[CONF_NAME]
            if home_conf[CONF_ROOMS] != []:
                rooms[home] = home_conf[CONF_ROOMS]
            homes.append(home)
    else:
        homes = home_data.get_home_names()

    devices = []
    for home in homes:
        _LOGGER.debug("Setting up %s ...", home)
        try:
            room_data = ThermostatData(auth, home)
        except pyatmo.NoDevice:
            continue
        for room_id in room_data.get_room_ids():
            room_name = room_data.homedata.rooms[home][room_id]['name']
            _LOGGER.debug("Setting up %s (%s) ...", room_name, room_id)
            if home in rooms and room_name not in rooms[home]:
                _LOGGER.debug("Excluding %s ...", room_name)
                continue
            _LOGGER.debug("Adding devices for room %s (%s) ...",
                          room_name, room_id)
            devices.append(NetatmoThermostat(room_data, room_id))
    add_entities(devices, True)


class NetatmoThermostat(ClimateDevice):
    """Representation a Netatmo thermostat."""

    def __init__(self, data, room_id):
        """Initialize the sensor."""
        self._data = data
        self._state = None
        self._room_id = room_id
        room_name = self._data.homedata.rooms[self._data.home][room_id]['name']
        self._name = 'netatmo_{}'.format(room_name)
        self._target_temperature = None
        self._away = None
        self._module_type = self._data.room_status[room_id]['module_type']
        if self._module_type == NA_VALVE:
            self._operation_list = [DICT_NETATMO_TO_HA[STATE_NETATMO_SCHEDULE],
                                    DICT_NETATMO_TO_HA[STATE_NETATMO_MANUAL],
                                    DICT_NETATMO_TO_HA[STATE_NETATMO_AWAY],
                                    DICT_NETATMO_TO_HA[STATE_NETATMO_HG]]
            self._support_flags = SUPPORT_FLAGS
        elif self._module_type == NA_THERM:
            self._operation_list = [DICT_NETATMO_TO_HA[STATE_NETATMO_SCHEDULE],
                                    DICT_NETATMO_TO_HA[STATE_NETATMO_MANUAL],
                                    DICT_NETATMO_TO_HA[STATE_NETATMO_AWAY],
                                    DICT_NETATMO_TO_HA[STATE_NETATMO_HG],
                                    DICT_NETATMO_TO_HA[STATE_NETATMO_MAX],
                                    DICT_NETATMO_TO_HA[STATE_NETATMO_OFF]]
            self._support_flags = SUPPORT_FLAGS | SUPPORT_ON_OFF
        self._operation_mode = None
        self.update_without_throttle = False

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._support_flags

    @property
    def name(self):
        """Return the name of the thermostat."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._data.room_status[self._room_id]['current_temperature']

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._data.room_status[self._room_id]['target_temperature']

    @property
    def current_operation(self):
        """Return the current state of the thermostat."""
        return self._operation_mode

    @property
    def operation_list(self):
        """Return the operation modes list."""
        return self._operation_list

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        module_type = self._data.room_status[self._room_id]['module_type']
        if module_type not in (NA_THERM, NA_VALVE):
            return {}
        state_attributes = {
            "home_id": self._data.homedata.gethomeId(self._data.home),
            "room_id": self._room_id,
            "setpoint_default_duration": self._data.setpoint_duration,
            "away_temperature": self._data.away_temperature,
            "hg_temperature": self._data.hg_temperature,
            "operation_mode": self._operation_mode,
            "module_type": module_type,
            "module_id": self._data.room_status[self._room_id]['module_id']
        }
        if module_type == NA_THERM:
            state_attributes["boiler_status"] = self._data.boilerstatus
        elif module_type == NA_VALVE:
            state_attributes["heating_power_request"] = \
                self._data.room_status[self._room_id]['heating_power_request']
        return state_attributes

    @property
    def is_away_mode_on(self):
        """Return true if away mode is on."""
        return self._away

    @property
    def is_on(self):
        """Return true if on."""
        return self.target_temperature > 0

    def turn_away_mode_on(self):
        """Turn away on."""
        self.set_operation_mode(DICT_NETATMO_TO_HA[STATE_NETATMO_AWAY])

    def turn_away_mode_off(self):
        """Turn away off."""
        self.set_operation_mode(DICT_NETATMO_TO_HA[STATE_NETATMO_SCHEDULE])

    def turn_off(self):
        """Turn Netatmo off."""
        _LOGGER.debug("Switching off ...")
        self.set_operation_mode(DICT_NETATMO_TO_HA[STATE_NETATMO_OFF])
        self.update_without_throttle = True
        self.schedule_update_ha_state()

    def turn_on(self):
        """Turn Netatmo on."""
        _LOGGER.debug("Switching on ...")
        _LOGGER.debug("Setting temperature first to %d ...",
                      self._data.hg_temperature)
        self._data.homestatus.setroomThermpoint(
            self._data.homedata.gethomeId(self._data.home),
            self._room_id, STATE_NETATMO_MANUAL, self._data.hg_temperature)
        _LOGGER.debug("Setting operation mode to schedule ...")
        self._data.homestatus.setThermmode(
            self._data.homedata.gethomeId(self._data.home),
            STATE_NETATMO_SCHEDULE)
        self.update_without_throttle = True
        self.schedule_update_ha_state()

    def set_operation_mode(self, operation_mode):
        """Set HVAC mode (auto, auxHeatOnly, cool, heat, off)."""
        if not self.is_on:
            self.turn_on()
        if operation_mode in [DICT_NETATMO_TO_HA[STATE_NETATMO_MAX],
                              DICT_NETATMO_TO_HA[STATE_NETATMO_OFF]]:
            self._data.homestatus.setroomThermpoint(
                self._data.homedata.gethomeId(self._data.home),
                self._room_id, DICT_HA_TO_NETATMO[operation_mode])
        elif operation_mode in [DICT_NETATMO_TO_HA[STATE_NETATMO_HG],
                                DICT_NETATMO_TO_HA[STATE_NETATMO_SCHEDULE],
                                DICT_NETATMO_TO_HA[STATE_NETATMO_AWAY]]:
            self._data.homestatus.setThermmode(
                self._data.homedata.gethomeId(self._data.home),
                DICT_HA_TO_NETATMO[operation_mode])
        self.update_without_throttle = True
        self.schedule_update_ha_state()

    def set_temperature(self, **kwargs):
        """Set new target temperature for 2 hours."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        mode = STATE_NETATMO_MANUAL
        self._data.homestatus.setroomThermpoint(
            self._data.homedata.gethomeId(self._data.home),
            self._room_id, DICT_HA_TO_NETATMO[mode], temp)
        self.update_without_throttle = True
        self.schedule_update_ha_state()

    def update(self):
        """Get the latest data from NetAtmo API and updates the states."""
        try:
            if self.update_without_throttle:
                self._data.update(no_throttle=True)
                self.update_without_throttle = False
            else:
                self._data.update()
        except AttributeError:
            _LOGGER.error("NetatmoThermostat::update() "
                          "got exception.")
            return
        self._target_temperature = \
            self._data.room_status[self._room_id]['target_temperature']
        self._operation_mode = DICT_NETATMO_TO_HA[
            self._data.room_status[self._room_id]['setpoint_mode']]
        self._away = self._operation_mode == DICT_NETATMO_TO_HA[
            STATE_NETATMO_AWAY]


class HomeData:
    """Representation Netatmo homes."""

    def __init__(self, auth, home=None):
        """Initialize the HomeData object."""
        self.auth = auth
        self.homedata = None
        self.home_names = []
        self.room_names = []
        self.schedules = []
        self.home = home
        self.home_id = None

    def get_home_names(self):
        """Get all the home names returned by NetAtmo API."""
        self.setup()
        if self.homedata is None:
            return []
        for home in self.homedata.homes:
            if 'therm_schedules' in self.homedata.homes[home] and 'modules' \
               in self.homedata.homes[home]:
                self.home_names.append(self.homedata.homes[home]['name'])
        return self.home_names

    def setup(self):
        """Retrieve HomeData by NetAtmo API."""
        import pyatmo
        try:
            self.homedata = pyatmo.HomeData(self.auth)
            self.home_id = self.homedata.gethomeId(self.home)
        except TypeError:
            _LOGGER.error("Error when getting home data.")
        except AttributeError:
            _LOGGER.error("No default_home in HomeData.")
        except pyatmo.NoDevice:
            _LOGGER.debug("No thermostat devices available.")


class ThermostatData:
    """Get the latest data from Netatmo."""

    def __init__(self, auth, home=None):
        """Initialize the data object."""
        self.auth = auth
        self.homedata = None
        self.homestatus = None
        self.room_ids = []
        self.room_status = {}
        self.schedules = []
        self.home = home
        self.away_temperature = None
        self.hg_temperature = None
        self.boilerstatus = None
        self.setpoint_duration = None
        self.home_id = None

    def get_room_ids(self):
        """Return all module available on the API as a list."""
        if not self.setup():
            return []
        for key in self.homestatus.rooms:
            self.room_ids.append(key)
        return self.room_ids

    def setup(self):
        """Retrieve HomeData and HomeStatus by NetAtmo API."""
        import pyatmo
        try:
            self.homedata = pyatmo.HomeData(self.auth)
            self.homestatus = pyatmo.HomeStatus(self.auth, home=self.home)
            self.home_id = self.homedata.gethomeId(self.home)
            self.update()
        except TypeError:
            _LOGGER.error("ThermostatData::setup() got error.")
            return False
        return True

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Call the NetAtmo API to update the data."""
        import pyatmo
        try:
            self.homestatus = pyatmo.HomeStatus(self.auth, home=self.home)
        except TypeError:
            _LOGGER.error("Error when getting homestatus.")
            return
        _LOGGER.debug("Following is the debugging output for homestatus:")
        _LOGGER.debug(self.homestatus.rawData)
        for key in self.homestatus.rooms:
            roomstatus = {}
            homestatus_room = self.homestatus.rooms[key]
            homedata_room = self.homedata.rooms[self.home][key]
            roomstatus['roomID'] = homestatus_room['id']
            roomstatus['roomname'] = homedata_room['name']
            roomstatus['target_temperature'] = \
                homestatus_room['therm_setpoint_temperature']
            roomstatus['setpoint_mode'] = \
                homestatus_room['therm_setpoint_mode']
            roomstatus['current_temperature'] = \
                homestatus_room['therm_measured_temperature']
            roomstatus['module_type'] = \
                self.homestatus.thermostatType(self.home, key)
            roomstatus['module_id'] = None
            roomstatus['heating_status'] = None
            roomstatus['heating_power_request'] = None
            for module_id in homedata_room['module_ids']:
                if self.homedata.modules[self.home][module_id]['type'] == \
                   NA_THERM or roomstatus['module_id'] is None:
                    roomstatus['module_id'] = module_id
            if roomstatus['module_type'] == NA_THERM:
                self.boilerstatus = self.homestatus.boilerStatus(
                    rid=roomstatus['module_id'])
                roomstatus['heating_status'] = self.boilerstatus
            elif roomstatus['module_type'] == NA_VALVE:
                roomstatus['heating_power_request'] = \
                    homestatus_room['heating_power_request']
                roomstatus['heating_status'] = \
                    roomstatus['heating_power_request'] > 0
                if self.boilerstatus is not None:
                    roomstatus['heating_status'] = \
                      self.boilerstatus and roomstatus['heating_status']
            self.room_status[key] = roomstatus
        self.away_temperature = self.homestatus.getAwaytemp(self.home)
        self.hg_temperature = self.homestatus.getHgtemp(self.home)
        self.setpoint_duration = self.homedata.setpoint_duration[self.home]
