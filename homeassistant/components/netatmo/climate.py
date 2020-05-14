"""Support for Netatmo Smart thermostats."""
from datetime import timedelta
import logging
from typing import List, Optional

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
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_HOME_NAME,
    ATTR_SCHEDULE_NAME,
    DATA_HANDLER,
    DOMAIN,
    MANUFACTURER,
    MODELS,
    SERVICE_SETSCHEDULE,
)
from .netatmo_entity_base import NetatmoBase

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
STATE_NETATMO_HOME = "home"

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
    data_handler = hass.data[DOMAIN][entry.entry_id][DATA_HANDLER]

    data_class = "HomeData"
    await data_handler.register_data_class(data_class)
    home_data = data_handler.data.get(data_class)

    async def get_entities():
        """Retrieve Netatmo entities."""
        entities = []

        def get_all_home_ids():
            """Get all the home ids returned by NetAtmo API."""
            if home_data is None:
                return []
            home_ids = []
            for home_id in home_data.homes:
                if (
                    "therm_schedules" in home_data.homes[home_id]
                    and "modules" in home_data.homes[home_id]
                ):
                    home_ids.append(home_data.homes[home_id]["id"])
            return home_ids

        home_ids = get_all_home_ids()

        def get_room_ids(home_id):
            """Return all module available on the API as a list."""
            room_ids = []
            for room in home_data.rooms[home_id]:
                room_ids.append(room)
            return room_ids

        for home_id in home_ids:
            _LOGGER.debug("Setting up home %s ...", home_id)
            for room_id in get_room_ids(home_id):
                room_name = home_data.rooms[home_id][room_id]["name"]
                _LOGGER.debug("Setting up room %s (%s) ...", room_name, room_id)
                await data_handler.register_data_class("HomeStatus", home_id=home_id)
                if room_id in data_handler.data[f"HomeStatus-{home_id}"].rooms:
                    entities.append(
                        NetatmoThermostat(data_handler, data_class, home_id, room_id)
                    )
                else:
                    await data_handler.unregister_data_class(f"HomeStatus-{home_id}")

        return entities

    async_add_entities(await get_entities(), True)

    def _service_setschedule(service):
        """Service to change current home schedule."""
        home_name = service.data.get(ATTR_HOME_NAME)
        schedule_name = service.data.get(ATTR_SCHEDULE_NAME)
        home_data.switchHomeSchedule(schedule=schedule_name, home=home_name)
        _LOGGER.info("Set home (%s) schedule to %s", home_name, schedule_name)

    if home_data is not None:
        hass.services.async_register(
            DOMAIN,
            SERVICE_SETSCHEDULE,
            _service_setschedule,
            schema=SCHEMA_SERVICE_SETSCHEDULE,
        )


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Netatmo energy sensors."""
    return


class NetatmoThermostat(ClimateDevice, NetatmoBase):
    """Representation a Netatmo thermostat."""

    def __init__(self, data_handler, data_class, home_id, room_id):
        """Initialize the sensor."""
        ClimateDevice.__init__(self)
        NetatmoBase.__init__(self, data_handler)

        self._data_class = data_class

        self._home_status = self.data_handler.data[f"HomeStatus-{home_id}"]
        self._room_status = self._home_status.rooms[room_id]
        self._room_data = self._data.rooms[home_id][room_id]

        self._state = None
        self._room_id = room_id
        self._home_id = home_id
        self._room_name = self._data.rooms[home_id][room_id]["name"]
        self._name = f"{MANUFACTURER} {self._room_name}"
        self._current_temperature = None
        self._target_temperature = None
        self._preset = None
        self._away = None
        self._operation_list = [HVAC_MODE_AUTO, HVAC_MODE_HEAT]
        self._support_flags = SUPPORT_FLAGS
        self._hvac_mode = None
        self._battery_level = None
        self._connected = None
        self.update_without_throttle = False
        self._module_type = self._room_status.get(room_id, {}).get(
            "module_type", NA_VALVE
        )

        self._away_temperature = None
        self._hg_temperature = None
        self._boilerstatus = None
        self._setpoint_duration = None

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
            return CURRENT_HVAC_MAP_NETATMO[self._boilerstatus]
        # Maybe it is a valve
        if self._room_status:
            if self._room_status.get("heating_power_request", 0) > 0:
                return CURRENT_HVAC_HEAT
        return CURRENT_HVAC_IDLE

    def set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVAC_MODE_OFF:
            self.turn_off()
        elif hvac_mode == HVAC_MODE_AUTO:
            if self.hvac_mode == HVAC_MODE_OFF:
                self.turn_on()
            self.set_preset_mode(PRESET_SCHEDULE)
        elif hvac_mode == HVAC_MODE_HEAT:
            self.set_preset_mode(PRESET_BOOST)

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if self.target_temperature == 0:
            self._home_status.setroomThermpoint(
                self._room_id, STATE_NETATMO_HOME,
            )

        if (
            preset_mode in [PRESET_BOOST, STATE_NETATMO_MAX]
            and self._module_type == NA_VALVE
        ):
            self._home_status.setroomThermpoint(
                self._room_id, STATE_NETATMO_MANUAL, DEFAULT_MAX_TEMP,
            )
        elif preset_mode in [PRESET_BOOST, STATE_NETATMO_MAX]:
            self._home_status.setroomThermpoint(
                self._room_id, PRESET_MAP_NETATMO[preset_mode]
            )
        elif preset_mode in [PRESET_SCHEDULE, PRESET_FROST_GUARD, PRESET_AWAY]:
            self._home_status.setThermmode(PRESET_MAP_NETATMO[preset_mode])
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
        self._home_status.setroomThermpoint(self._room_id, STATE_NETATMO_MANUAL, temp)

        self.update_without_throttle = True
        self.schedule_update_ha_state()

    @property
    def device_state_attributes(self):
        """Return the state attributes of the thermostat."""
        attr = {}

        if self._battery_level is not None:
            attr[ATTR_BATTERY_LEVEL] = self._battery_level

        return attr

    def turn_off(self):
        """Turn the entity off."""
        if self._module_type == NA_VALVE:
            self._home_status.setroomThermpoint(
                self._room_id, STATE_NETATMO_MANUAL, DEFAULT_MIN_TEMP,
            )
        elif self.hvac_mode != HVAC_MODE_OFF:
            self._home_status.setroomThermpoint(self._room_id, STATE_NETATMO_OFF)
        self.update_without_throttle = True
        self.schedule_update_ha_state()

    def turn_on(self):
        """Turn the entity on."""
        self._home_status.setroomThermpoint(self._room_id, STATE_NETATMO_HOME)
        self.update_without_throttle = True
        self.schedule_update_ha_state()

    @property
    def available(self) -> bool:
        """If the device hasn't been able to connect, mark as unavailable."""
        return bool(self._connected)

    @callback
    def async_update_callback(self):
        """Update the entity's state."""
        try:
            roomstatus = {}

            self._home_status = self.data_handler.data[f"HomeStatus-{self._home_id}"]
            self._room_status = self._home_status.rooms[self._room_id]
            self._room_data = self._data.rooms[self._home_id][self._room_id]

            roomstatus["roomID"] = self._room_status["id"]
            if self._room_status["reachable"]:
                roomstatus["roomname"] = self._room_data["name"]
                roomstatus["target_temperature"] = self._room_status[
                    "therm_setpoint_temperature"
                ]
                roomstatus["setpoint_mode"] = self._room_status["therm_setpoint_mode"]
                roomstatus["current_temperature"] = self._room_status[
                    "therm_measured_temperature"
                ]
                roomstatus["module_type"] = self._data.get_thermostat_type(
                    home_id=self._home_id, room_id=self._room_id,
                )
                roomstatus["module_id"] = None
                roomstatus["heating_status"] = None
                roomstatus["heating_power_request"] = None
                batterylevel = None
                for module_id in self._room_data["module_ids"]:
                    if (
                        self._data.modules[self._home_id][module_id]["type"] == NA_THERM
                        or roomstatus["module_id"] is None
                    ):
                        roomstatus["module_id"] = module_id
                if roomstatus["module_type"] == NA_THERM:
                    self._boilerstatus = self._home_status.boiler_status(
                        roomstatus["module_id"]
                    )
                    roomstatus["heating_status"] = self._boilerstatus
                    batterylevel = self._home_status.thermostats[
                        roomstatus["module_id"]
                    ].get("battery_level")
                elif roomstatus["module_type"] == NA_VALVE:
                    roomstatus["heating_power_request"] = self._room_status[
                        "heating_power_request"
                    ]
                    roomstatus["heating_status"] = (
                        roomstatus["heating_power_request"] > 0
                    )
                    if self._boilerstatus is not None:
                        roomstatus["heating_status"] = (
                            self._boilerstatus and roomstatus["heating_status"]
                        )
                    batterylevel = self._home_status.valves[
                        roomstatus["module_id"]
                    ].get("battery_level")

                if batterylevel:
                    batterypct = interpolate(batterylevel, roomstatus["module_type"])
                    if roomstatus.get("battery_level") is None:
                        roomstatus["battery_level"] = batterypct
                    elif batterypct < roomstatus["battery_level"]:
                        roomstatus["battery_level"] = batterypct
        except KeyError as err:
            _LOGGER.error("Update of room %s failed. Error: %s", self._room_id, err)

        self._away_temperature = self._data.get_away_temp(self._home_id)
        self._hg_temperature = self._data.get_hg_temp(self._home_id)
        self._setpoint_duration = self._data.setpoint_duration[self._home_id]

        try:
            if self._module_type is None:
                self._module_type = roomstatus["module_type"]
            self._current_temperature = roomstatus["current_temperature"]
            self._target_temperature = roomstatus["target_temperature"]
            self._preset = NETATMO_MAP_PRESET[roomstatus["setpoint_mode"]]
            self._hvac_mode = HVAC_MAP_NETATMO[self._preset]
            self._battery_level = roomstatus.get("battery_level")
            self._connected = True
        except KeyError as err:
            if self._connected is not False:
                _LOGGER.debug(
                    "The thermostat in room %s seems to be out of reach. (%s)",
                    self._room_name,
                    err,
                )
            self._connected = False

        self._away = self._hvac_mode == HVAC_MAP_NETATMO[STATE_NETATMO_AWAY]


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
