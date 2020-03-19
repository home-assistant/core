"""Support for Netatmo Smart thermostats."""
from datetime import timedelta
import logging
from typing import List, Optional

import pyatmo
import requests
import voluptuous as vol

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    DEFAULT_MIN_TEMP,
    HVAC_MODE_AUTO,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_AWAY,
    PRESET_BOOST,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    ATTR_TEMPERATURE,
    PRECISION_HALVES,
    STATE_OFF,
    TEMP_CELSIUS,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.util import Throttle

from .const import (
    ATTR_HOME_NAME,
    ATTR_SCHEDULE_NAME,
    AUTH,
    DOMAIN,
    MANUFACTURER,
    MODELS,
    SERVICE_SETSCHEDULE,
)

_LOGGER = logging.getLogger(__name__)

PRESET_FROST_GUARD = "Frost Guard"
PRESET_SCHEDULE = "Schedule"
PRESET_MANUAL = "Manual"

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE
SUPPORT_HVAC = [HVAC_MODE_HEAT, HVAC_MODE_AUTO, HVAC_MODE_OFF]
SUPPORT_PRESET = [PRESET_AWAY, PRESET_BOOST, PRESET_FROST_GUARD, PRESET_SCHEDULE]

STATE_NETATMO_SCHEDULE = "schedule"
STATE_NETATMO_HG = "hg"
STATE_NETATMO_MAX = "max"
STATE_NETATMO_AWAY = PRESET_AWAY
STATE_NETATMO_OFF = STATE_OFF
STATE_NETATMO_MANUAL = "manual"

PRESET_MAP_NETATMO = {
    PRESET_FROST_GUARD: STATE_NETATMO_HG,
    PRESET_BOOST: STATE_NETATMO_MAX,
    PRESET_SCHEDULE: STATE_NETATMO_SCHEDULE,
    PRESET_AWAY: STATE_NETATMO_AWAY,
    STATE_NETATMO_OFF: STATE_NETATMO_OFF,
}

NETATMO_MAP_PRESET = {
    STATE_NETATMO_HG: PRESET_FROST_GUARD,
    STATE_NETATMO_MAX: PRESET_BOOST,
    STATE_NETATMO_SCHEDULE: PRESET_SCHEDULE,
    STATE_NETATMO_AWAY: PRESET_AWAY,
    STATE_NETATMO_OFF: STATE_NETATMO_OFF,
    STATE_NETATMO_MANUAL: STATE_NETATMO_MANUAL,
}

HVAC_MAP_NETATMO = {
    PRESET_SCHEDULE: HVAC_MODE_AUTO,
    STATE_NETATMO_HG: HVAC_MODE_AUTO,
    PRESET_FROST_GUARD: HVAC_MODE_AUTO,
    PRESET_BOOST: HVAC_MODE_HEAT,
    STATE_NETATMO_OFF: HVAC_MODE_OFF,
    STATE_NETATMO_MANUAL: HVAC_MODE_AUTO,
    PRESET_MANUAL: HVAC_MODE_AUTO,
    STATE_NETATMO_AWAY: HVAC_MODE_AUTO,
}

CURRENT_HVAC_MAP_NETATMO = {True: CURRENT_HVAC_HEAT, False: CURRENT_HVAC_IDLE}

CONF_HOMES = "homes"
CONF_ROOMS = "rooms"

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=300)

DEFAULT_MAX_TEMP = 30

NA_THERM = "NATherm1"
NA_VALVE = "NRV"

SCHEMA_SERVICE_SETSCHEDULE = vol.Schema(
    {
        vol.Required(ATTR_SCHEDULE_NAME): cv.string,
        vol.Required(ATTR_HOME_NAME): cv.string,
    }
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Netatmo energy platform."""
    auth = hass.data[DOMAIN][entry.entry_id][AUTH]

    home_data = HomeData(auth)

    def get_entities():
        """Retrieve Netatmo entities."""
        entities = []
        try:
            home_data.setup()
        except pyatmo.NoDevice:
            return
        home_ids = home_data.get_all_home_ids()

        for home_id in home_ids:
            _LOGGER.debug("Setting up home %s ...", home_id)
            try:
                room_data = ThermostatData(auth, home_id)
            except pyatmo.NoDevice:
                continue
            for room_id in room_data.get_room_ids():
                room_name = room_data.homedata.rooms[home_id][room_id]["name"]
                _LOGGER.debug("Setting up room %s (%s) ...", room_name, room_id)
                entities.append(NetatmoThermostat(room_data, room_id))
        return entities

    async_add_entities(await hass.async_add_executor_job(get_entities), True)

    def _service_setschedule(service):
        """Service to change current home schedule."""
        home_name = service.data.get(ATTR_HOME_NAME)
        schedule_name = service.data.get(ATTR_SCHEDULE_NAME)
        home_data.homedata.switchHomeSchedule(schedule=schedule_name, home=home_name)
        _LOGGER.info("Set home (%s) schedule to %s", home_name, schedule_name)

    if home_data.homedata is not None:
        hass.services.async_register(
            DOMAIN,
            SERVICE_SETSCHEDULE,
            _service_setschedule,
            schema=SCHEMA_SERVICE_SETSCHEDULE,
        )


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Netatmo energy sensors."""
    return


class NetatmoThermostat(ClimateDevice):
    """Representation a Netatmo thermostat."""

    def __init__(self, data, room_id):
        """Initialize the sensor."""
        self._data = data
        self._state = None
        self._room_id = room_id
        self._room_name = self._data.homedata.rooms[self._data.home_id][room_id]["name"]
        self._name = f"{MANUFACTURER} {self._room_name}"
        self._current_temperature = None
        self._target_temperature = None
        self._preset = None
        self._away = None
        self._operation_list = [HVAC_MODE_AUTO, HVAC_MODE_HEAT]
        self._support_flags = SUPPORT_FLAGS
        self._hvac_mode = None
        self._battery_level = None
        self.update_without_throttle = False
        self._module_type = self._data.room_status.get(room_id, {}).get("module_type")

        if self._module_type == NA_THERM:
            self._operation_list.append(HVAC_MODE_OFF)

        self._unique_id = f"{self._room_id}-{self._module_type}"

    @property
    def device_info(self):
        """Return the device info for the thermostat/valve."""
        return {
            "identifiers": {(DOMAIN, self._room_id)},
            "name": self._room_name,
            "manufacturer": MANUFACTURER,
            "model": MODELS[self._module_type],
        }

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

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
            if (
                self._data.room_status[self._room_id].get("heating_power_request", 0)
                > 0
            ):
                return CURRENT_HVAC_HEAT
        return CURRENT_HVAC_IDLE

    def set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""
        mode = None

        if hvac_mode == HVAC_MODE_OFF:
            mode = STATE_NETATMO_OFF
        elif hvac_mode == HVAC_MODE_AUTO:
            mode = PRESET_SCHEDULE
        elif hvac_mode == HVAC_MODE_HEAT:
            mode = PRESET_BOOST

        self.set_preset_mode(mode)

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if self.target_temperature == 0:
            self._data.homestatus.setroomThermpoint(
                self._data.home_id,
                self._room_id,
                STATE_NETATMO_MANUAL,
                DEFAULT_MIN_TEMP,
            )

        if (
            preset_mode in [PRESET_BOOST, STATE_NETATMO_MAX]
            and self._module_type == NA_VALVE
        ):
            self._data.homestatus.setroomThermpoint(
                self._data.home_id,
                self._room_id,
                STATE_NETATMO_MANUAL,
                DEFAULT_MAX_TEMP,
            )
        elif preset_mode in [PRESET_BOOST, STATE_NETATMO_MAX, STATE_NETATMO_OFF]:
            self._data.homestatus.setroomThermpoint(
                self._data.home_id, self._room_id, PRESET_MAP_NETATMO[preset_mode]
            )
        elif preset_mode in [PRESET_SCHEDULE, PRESET_FROST_GUARD, PRESET_AWAY]:
            self._data.homestatus.setThermmode(
                self._data.home_id, PRESET_MAP_NETATMO[preset_mode]
            )
        else:
            _LOGGER.error("Preset mode '%s' not available", preset_mode)
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
            self._data.home_id, self._room_id, STATE_NETATMO_MANUAL, temp
        )

        self.update_without_throttle = True
        self.schedule_update_ha_state()

    @property
    def device_state_attributes(self):
        """Return the state attributes of the thermostat."""
        attr = {}

        if self._battery_level is not None:
            attr[ATTR_BATTERY_LEVEL] = self._battery_level

        return attr

    def update(self):
        """Get the latest data from NetAtmo API and updates the states."""
        try:
            if self.update_without_throttle:
                self._data.update(no_throttle=True)
                self.update_without_throttle = False
            else:
                self._data.update()
        except AttributeError:
            _LOGGER.error("NetatmoThermostat::update() got exception")
            return
        try:
            if self._module_type is None:
                self._module_type = self._data.room_status[self._room_id]["module_type"]
            self._current_temperature = self._data.room_status[self._room_id][
                "current_temperature"
            ]
            self._target_temperature = self._data.room_status[self._room_id][
                "target_temperature"
            ]
            self._preset = NETATMO_MAP_PRESET[
                self._data.room_status[self._room_id]["setpoint_mode"]
            ]
            self._hvac_mode = HVAC_MAP_NETATMO[self._preset]
            self._battery_level = self._data.room_status[self._room_id].get(
                "battery_level"
            )
        except KeyError as err:
            _LOGGER.error(
                "The thermostat in room %s seems to be out of reach. (%s)",
                self._room_name,
                err,
            )
        self._away = self._hvac_mode == HVAC_MAP_NETATMO[STATE_NETATMO_AWAY]


class HomeData:
    """Representation Netatmo homes."""

    def __init__(self, auth, home=None):
        """Initialize the HomeData object."""
        self.auth = auth
        self.homedata = None
        self.home_ids = []
        self.home_names = []
        self.room_names = []
        self.schedules = []
        self.home = home
        self.home_id = None

    def get_all_home_ids(self):
        """Get all the home ids returned by NetAtmo API."""
        if self.homedata is None:
            return []
        for home_id in self.homedata.homes:
            if (
                "therm_schedules" in self.homedata.homes[home_id]
                and "modules" in self.homedata.homes[home_id]
            ):
                self.home_ids.append(self.homedata.homes[home_id]["id"])
        return self.home_ids

    def setup(self):
        """Retrieve HomeData by NetAtmo API."""
        try:
            self.homedata = pyatmo.HomeData(self.auth)
            self.home_id = self.homedata.gethomeId(self.home)
        except TypeError:
            _LOGGER.error("Error when getting home data")
        except AttributeError:
            _LOGGER.error("No default_home in HomeData")
        except pyatmo.NoDevice:
            _LOGGER.debug("No thermostat devices available")
        except pyatmo.InvalidHome:
            _LOGGER.debug("Invalid home %s", self.home)


class ThermostatData:
    """Get the latest data from Netatmo."""

    def __init__(self, auth, home_id=None):
        """Initialize the data object."""
        self.auth = auth
        self.homedata = None
        self.homestatus = None
        self.room_ids = []
        self.room_status = {}
        self.schedules = []
        self.home_id = home_id
        self.home_name = None
        self.away_temperature = None
        self.hg_temperature = None
        self.boilerstatus = None
        self.setpoint_duration = None

    def get_room_ids(self):
        """Return all module available on the API as a list."""
        if not self.setup():
            return []
        for room in self.homestatus.rooms:
            self.room_ids.append(room)
        return self.room_ids

    def setup(self):
        """Retrieve HomeData and HomeStatus by NetAtmo API."""
        try:
            self.homedata = pyatmo.HomeData(self.auth)
            self.homestatus = pyatmo.HomeStatus(self.auth, home_id=self.home_id)
            self.home_name = self.homedata.getHomeName(self.home_id)
            self.update()
        except TypeError:
            _LOGGER.error("ThermostatData::setup() got error")
            return False
        return True

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Call the NetAtmo API to update the data."""
        try:
            self.homestatus = pyatmo.HomeStatus(self.auth, home_id=self.home_id)
        except pyatmo.exceptions.NoDevice:
            _LOGGER.error("No device found")
            return
        except TypeError:
            _LOGGER.error("Error when getting homestatus")
            return
        except requests.exceptions.Timeout:
            _LOGGER.warning("Timed out when connecting to Netatmo server")
            return
        for room in self.homestatus.rooms:
            try:
                roomstatus = {}
                homestatus_room = self.homestatus.rooms[room]
                homedata_room = self.homedata.rooms[self.home_id][room]

                roomstatus["roomID"] = homestatus_room["id"]
                if homestatus_room["reachable"]:
                    roomstatus["roomname"] = homedata_room["name"]
                    roomstatus["target_temperature"] = homestatus_room[
                        "therm_setpoint_temperature"
                    ]
                    roomstatus["setpoint_mode"] = homestatus_room["therm_setpoint_mode"]
                    roomstatus["current_temperature"] = homestatus_room[
                        "therm_measured_temperature"
                    ]
                    roomstatus["module_type"] = self.homestatus.thermostatType(
                        home_id=self.home_id, rid=room, home=self.home_name
                    )
                    roomstatus["module_id"] = None
                    roomstatus["heating_status"] = None
                    roomstatus["heating_power_request"] = None
                    batterylevel = None
                    for module_id in homedata_room["module_ids"]:
                        if (
                            self.homedata.modules[self.home_id][module_id]["type"]
                            == NA_THERM
                            or roomstatus["module_id"] is None
                        ):
                            roomstatus["module_id"] = module_id
                    if roomstatus["module_type"] == NA_THERM:
                        self.boilerstatus = self.homestatus.boilerStatus(
                            rid=roomstatus["module_id"]
                        )
                        roomstatus["heating_status"] = self.boilerstatus
                        batterylevel = self.homestatus.thermostats[
                            roomstatus["module_id"]
                        ].get("battery_level")
                    elif roomstatus["module_type"] == NA_VALVE:
                        roomstatus["heating_power_request"] = homestatus_room[
                            "heating_power_request"
                        ]
                        roomstatus["heating_status"] = (
                            roomstatus["heating_power_request"] > 0
                        )
                        if self.boilerstatus is not None:
                            roomstatus["heating_status"] = (
                                self.boilerstatus and roomstatus["heating_status"]
                            )
                        batterylevel = self.homestatus.valves[
                            roomstatus["module_id"]
                        ].get("battery_level")

                    if batterylevel:
                        batterypct = interpolate(
                            batterylevel, roomstatus["module_type"]
                        )
                        if roomstatus.get("battery_level") is None:
                            roomstatus["battery_level"] = batterypct
                        elif batterypct < roomstatus["battery_level"]:
                            roomstatus["battery_level"] = batterypct
                self.room_status[room] = roomstatus
            except KeyError as err:
                _LOGGER.error("Update of room %s failed. Error: %s", room, err)
        self.away_temperature = self.homestatus.getAwaytemp(home_id=self.home_id)
        self.hg_temperature = self.homestatus.getHgtemp(home_id=self.home_id)
        self.setpoint_duration = self.homedata.setpoint_duration[self.home_id]


def interpolate(batterylevel, module_type):
    """Interpolate battery level depending on device type."""
    na_battery_levels = {
        NA_THERM: {
            "full": 4100,
            "high": 3600,
            "medium": 3300,
            "low": 3000,
            "empty": 2800,
        },
        NA_VALVE: {
            "full": 3200,
            "high": 2700,
            "medium": 2400,
            "low": 2200,
            "empty": 2200,
        },
    }

    levels = sorted(na_battery_levels[module_type].values())
    steps = [20, 50, 80, 100]

    na_battery_level = na_battery_levels[module_type]
    if batterylevel >= na_battery_level["full"]:
        return 100
    if batterylevel >= na_battery_level["high"]:
        i = 3
    elif batterylevel >= na_battery_level["medium"]:
        i = 2
    elif batterylevel >= na_battery_level["low"]:
        i = 1
    else:
        return 0

    pct = steps[i - 1] + (
        (steps[i] - steps[i - 1])
        * (batterylevel - levels[i])
        / (levels[i + 1] - levels[i])
    )
    return int(pct)
