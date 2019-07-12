"""Support for Netatmo Smart thermostats."""
from datetime import timedelta
import logging
from typing import Optional, List

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.climate import ClimateDevice, PLATFORM_SCHEMA
from homeassistant.components.climate.const import (
    HVAC_MODE_AUTO, HVAC_MODE_HEAT, HVAC_MODE_OFF,
    PRESET_AWAY, PRESET_BOOST,
    CURRENT_HVAC_HEAT, CURRENT_HVAC_IDLE,
    SUPPORT_TARGET_TEMPERATURE, SUPPORT_PRESET_MODE,
    DEFAULT_MIN_TEMP
)
from homeassistant.const import (
    TEMP_CELSIUS, ATTR_TEMPERATURE, CONF_NAME, PRECISION_HALVES, STATE_OFF)
from homeassistant.util import Throttle

from .const import DATA_NETATMO_AUTH

_LOGGER = logging.getLogger(__name__)

PRESET_FROST_GUARD = 'frost guard'
PRESET_SCHEDULE = 'schedule'

SUPPORT_FLAGS = (SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE)
SUPPORT_HVAC = [HVAC_MODE_HEAT, HVAC_MODE_AUTO, HVAC_MODE_OFF]
SUPPORT_PRESET = [
    PRESET_AWAY, PRESET_BOOST, PRESET_FROST_GUARD, PRESET_SCHEDULE,
]

STATE_NETATMO_SCHEDULE = PRESET_SCHEDULE
STATE_NETATMO_HG = 'hg'
STATE_NETATMO_MAX = 'max'
STATE_NETATMO_AWAY = PRESET_AWAY
STATE_NETATMO_OFF = STATE_OFF
STATE_NETATMO_MANUAL = 'manual'

PRESET_MAP_NETATMO = {
    PRESET_FROST_GUARD: STATE_NETATMO_HG,
    PRESET_BOOST: STATE_NETATMO_MAX,
    STATE_NETATMO_MAX: STATE_NETATMO_MAX,
    PRESET_SCHEDULE: STATE_NETATMO_SCHEDULE,
    PRESET_AWAY: STATE_NETATMO_AWAY,
    STATE_NETATMO_OFF: STATE_NETATMO_OFF
}

HVAC_MAP_NETATMO = {
    STATE_NETATMO_SCHEDULE: HVAC_MODE_AUTO,
    STATE_NETATMO_HG: HVAC_MODE_AUTO,
    STATE_NETATMO_MAX: HVAC_MODE_HEAT,
    STATE_NETATMO_OFF: HVAC_MODE_OFF,
    STATE_NETATMO_MANUAL: HVAC_MODE_AUTO,
    STATE_NETATMO_AWAY: HVAC_MODE_AUTO
}

CURRENT_HVAC_MAP_NETATMO = {
    True: CURRENT_HVAC_HEAT,
    False: CURRENT_HVAC_IDLE,
}

CONF_HOMES = 'homes'
CONF_ROOMS = 'rooms'

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=300)

HOME_CONFIG_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
    vol.Optional(CONF_ROOMS, default=[]): vol.All(cv.ensure_list, [cv.string])
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOMES): vol.All(cv.ensure_list, [HOME_CONFIG_SCHEMA])
})

DEFAULT_MAX_TEMP = 30

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
        self._room_name = self._data.homedata.rooms[
            self._data.home][room_id]['name']
        self._name = 'netatmo_{}'.format(self._room_name)
        self._current_temperature = None
        self._target_temperature = None
        self._preset = None
        self._away = None
        self._operation_list = [HVAC_MODE_AUTO, HVAC_MODE_HEAT]
        self._support_flags = SUPPORT_FLAGS
        self._hvac_mode = None
        self.update_without_throttle = False
        self._module_type = \
            self._data.room_status.get(room_id, {}).get('module_type')

        if self._module_type == NA_THERM:
            self._operation_list.append(HVAC_MODE_OFF)

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
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def target_temperature_step(self) -> Optional[float]:
        """Return the supported step of target temperature."""
        return PRECISION_HALVES

    @property
    def hvac_mode(self):
        """Return hvac operation ie. heat, cool mode."""
        return self._hvac_mode

    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes."""
        return self._operation_list

    @property
    def hvac_action(self) -> Optional[str]:
        """Return the current running hvac operation if supported."""
        if self._module_type == NA_THERM:
            return CURRENT_HVAC_MAP_NETATMO[self._data.boilerstatus]
        # Maybe it is a valve
        if self._room_id in self._data.room_status:
            if (self._data.room_status[self._room_id]
                    .get('heating_power_request', 0) > 0):
                return CURRENT_HVAC_HEAT
        return CURRENT_HVAC_IDLE

    def set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""
        mode = None

        if hvac_mode == HVAC_MODE_OFF:
            mode = STATE_NETATMO_OFF
        elif hvac_mode == HVAC_MODE_AUTO:
            mode = STATE_NETATMO_SCHEDULE
        elif hvac_mode == HVAC_MODE_HEAT:
            mode = STATE_NETATMO_MAX

        self.set_preset_mode(mode)

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if self.target_temperature == 0:
            self._data.homestatus.setroomThermpoint(
                self._data.home_id,
                self._room_id,
                STATE_NETATMO_MANUAL,
                DEFAULT_MIN_TEMP
            )

        if (
                preset_mode in [PRESET_BOOST, STATE_NETATMO_MAX]
                and self._module_type == NA_VALVE
        ):
            self._data.homestatus.setroomThermpoint(
                self._data.home_id,
                self._room_id,
                STATE_NETATMO_MANUAL,
                DEFAULT_MAX_TEMP
            )
        elif (
                preset_mode
                in [PRESET_BOOST, STATE_NETATMO_MAX, STATE_NETATMO_OFF]
        ):
            self._data.homestatus.setroomThermpoint(
                self._data.home_id,
                self._room_id,
                PRESET_MAP_NETATMO[preset_mode]
            )
        elif preset_mode in [
                PRESET_SCHEDULE, PRESET_FROST_GUARD, PRESET_AWAY
        ]:
            self._data.homestatus.setThermmode(
                self._data.home_id, PRESET_MAP_NETATMO[preset_mode]
            )
        self.update_without_throttle = True
        self.schedule_update_ha_state()

    @property
    def preset_mode(self) -> Optional[str]:
        """Return the current preset mode, e.g., home, away, temp."""
        return self._preset

    @property
    def preset_modes(self) -> Optional[List[str]]:
        """Return a list of available preset modes."""
        return SUPPORT_PRESET

    def set_temperature(self, **kwargs):
        """Set new target temperature for 2 hours."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        self._data.homestatus.setroomThermpoint(
            self._data.homedata.gethomeId(self._data.home),
            self._room_id, STATE_NETATMO_MANUAL, temp)

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
        try:
            if self._module_type is None:
                self._module_type = \
                    self._data.room_status[self._room_id]['module_type']
            self._current_temperature = \
                self._data.room_status[self._room_id]['current_temperature']
            self._target_temperature = \
                self._data.room_status[self._room_id]['target_temperature']
            self._preset = \
                self._data.room_status[self._room_id]["setpoint_mode"]
            self._hvac_mode = HVAC_MAP_NETATMO[self._preset]
        except KeyError:
            _LOGGER.error(
                "The thermostat in room %s seems to be out of reach.",
                self._room_id
            )
        self._away = self._hvac_mode == HVAC_MAP_NETATMO[STATE_NETATMO_AWAY]


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
            if (
                    'therm_schedules' in self.homedata.homes[home]
                    and 'modules' in self.homedata.homes[home]
            ):
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
        for room in self.homestatus.rooms:
            self.room_ids.append(room)
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
        except requests.exceptions.Timeout:
            _LOGGER.warning("Timed out when connecting to Netatmo server.")
            return
        _LOGGER.debug("Following is the debugging output for homestatus:")
        _LOGGER.debug(self.homestatus.rawData)
        for room in self.homestatus.rooms:
            try:
                roomstatus = {}
                homestatus_room = self.homestatus.rooms[room]
                homedata_room = self.homedata.rooms[self.home][room]

                roomstatus["roomID"] = homestatus_room["id"]
                if homestatus_room["reachable"]:
                    roomstatus["roomname"] = homedata_room["name"]
                    roomstatus["target_temperature"] = homestatus_room[
                        "therm_setpoint_temperature"
                    ]
                    roomstatus["setpoint_mode"] = homestatus_room[
                        "therm_setpoint_mode"
                    ]
                    roomstatus["current_temperature"] = homestatus_room[
                        "therm_measured_temperature"
                    ]
                    roomstatus["module_type"] = self.homestatus.thermostatType(
                        self.home, room
                    )
                    roomstatus["module_id"] = None
                    roomstatus["heating_status"] = None
                    roomstatus["heating_power_request"] = None
                    for module_id in homedata_room["module_ids"]:
                        if (self.homedata.modules[self.home][module_id]["type"]
                                == NA_THERM
                                or roomstatus["module_id"] is None):
                            roomstatus["module_id"] = module_id
                    if roomstatus["module_type"] == NA_THERM:
                        self.boilerstatus = self.homestatus.boilerStatus(
                            rid=roomstatus["module_id"]
                        )
                        roomstatus["heating_status"] = self.boilerstatus
                    elif roomstatus["module_type"] == NA_VALVE:
                        roomstatus["heating_power_request"] = homestatus_room[
                            "heating_power_request"
                        ]
                        roomstatus["heating_status"] = (
                            roomstatus["heating_power_request"] > 0
                        )
                        if self.boilerstatus is not None:
                            roomstatus["heating_status"] = (
                                self.boilerstatus
                                and roomstatus["heating_status"]
                            )
                self.room_status[room] = roomstatus
            except KeyError as err:
                _LOGGER.error("Update of room %s failed. Error: %s", room, err)
        self.away_temperature = self.homestatus.getAwaytemp(self.home)
        self.hg_temperature = self.homestatus.getHgtemp(self.home)
        self.setpoint_duration = self.homedata.setpoint_duration[self.home]
