"""Support for Netatmo Smart thermostats."""
import logging
from typing import List, Optional

import voluptuous as vol

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN, ClimateEntity
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
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    PRECISION_HALVES,
    STATE_OFF,
    TEMP_CELSIUS,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv, entity_platform

from .const import (
    ATTR_HEATING_POWER_REQUEST,
    ATTR_SCHEDULE_NAME,
    DATA_HANDLER,
    DATA_HOMES,
    DATA_SCHEDULES,
    DOMAIN,
    MANUFACTURER,
    SERVICE_SETSCHEDULE,
    SIGNAL_NAME,
)
from .data_handler import HOMEDATA_DATA_CLASS_NAME, HOMESTATUS_DATA_CLASS_NAME
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

DEFAULT_MAX_TEMP = 30

NA_THERM = "NATherm1"
NA_VALVE = "NRV"

SCHEMA_SERVICE_SETSCHEDULE = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_domain(CLIMATE_DOMAIN),
        vol.Required(ATTR_SCHEDULE_NAME): cv.string,
    }
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Netatmo energy platform."""
    data_handler = hass.data[DOMAIN][entry.entry_id][DATA_HANDLER]

    await data_handler.register_data_class(
        HOMEDATA_DATA_CLASS_NAME, HOMEDATA_DATA_CLASS_NAME, None
    )
    home_data = data_handler.data.get(HOMEDATA_DATA_CLASS_NAME)

    if not home_data:
        return

    async def get_entities():
        """Retrieve Netatmo entities."""
        entities = []

        for home_id in get_all_home_ids(home_data):
            _LOGGER.debug("Setting up home %s ...", home_id)
            for room_id in home_data.rooms[home_id].keys():
                room_name = home_data.rooms[home_id][room_id]["name"]
                _LOGGER.debug("Setting up room %s (%s) ...", room_name, room_id)
                signal_name = f"{HOMESTATUS_DATA_CLASS_NAME}-{home_id}"
                await data_handler.register_data_class(
                    HOMESTATUS_DATA_CLASS_NAME, signal_name, None, home_id=home_id
                )
                home_status = data_handler.data.get(signal_name)
                if home_status and room_id in home_status.rooms:
                    entities.append(NetatmoThermostat(data_handler, home_id, room_id))

            hass.data[DOMAIN][DATA_SCHEDULES][home_id] = {
                schedule_id: schedule_data.get("name")
                for schedule_id, schedule_data in (
                    data_handler.data[HOMEDATA_DATA_CLASS_NAME]
                    .schedules[home_id]
                    .items()
                )
            }

        hass.data[DOMAIN][DATA_HOMES] = {
            home_id: home_data.get("name")
            for home_id, home_data in (
                data_handler.data[HOMEDATA_DATA_CLASS_NAME].homes.items()
            )
        }

        return entities

    async_add_entities(await get_entities(), True)

    platform = entity_platform.current_platform.get()

    if home_data is not None:
        platform.async_register_entity_service(
            SERVICE_SETSCHEDULE, SCHEMA_SERVICE_SETSCHEDULE, "_service_setschedule",
        )


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Netatmo energy sensors."""
    return


class NetatmoThermostat(NetatmoBase, ClimateEntity):
    """Representation a Netatmo thermostat."""

    def __init__(self, data_handler, home_id, room_id):
        """Initialize the sensor."""
        ClimateEntity.__init__(self)
        super().__init__(data_handler)

        self._id = room_id
        self._home_id = home_id

        self._home_status_class = f"{HOMESTATUS_DATA_CLASS_NAME}-{self._home_id}"

        self._data_classes.extend(
            [
                {
                    "name": HOMEDATA_DATA_CLASS_NAME,
                    SIGNAL_NAME: HOMEDATA_DATA_CLASS_NAME,
                },
                {
                    "name": HOMESTATUS_DATA_CLASS_NAME,
                    "home_id": self._home_id,
                    SIGNAL_NAME: self._home_status_class,
                },
            ]
        )

        self._home_status = self.data_handler.data[self._home_status_class]
        self._room_status = self._home_status.rooms[room_id]
        self._room_data = self._data.rooms[home_id][room_id]

        self._model = NA_VALVE
        for module in self._room_data.get("module_ids"):
            if self._home_status.thermostats.get(module):
                self._model = NA_THERM
                break

        self._state = None
        self._device_name = self._data.rooms[home_id][room_id]["name"]
        self._name = f"{MANUFACTURER} {self._device_name}"
        self._current_temperature = None
        self._target_temperature = None
        self._preset = None
        self._away = None
        self._operation_list = [HVAC_MODE_AUTO, HVAC_MODE_HEAT]
        self._support_flags = SUPPORT_FLAGS
        self._hvac_mode = None
        self._battery_level = None
        self._connected = None

        self._away_temperature = None
        self._hg_temperature = None
        self._boilerstatus = None
        self._setpoint_duration = None

        if self._model == NA_THERM:
            self._operation_list.append(HVAC_MODE_OFF)

        self._unique_id = f"{self._id}-{self._model}"

    async def async_added_to_hass(self) -> None:
        """Entity created."""
        await super().async_added_to_hass()

        self._listeners.append(
            self.hass.bus.async_listen("netatmo_event", self.handle_event)
        )

    async def handle_event(self, event):
        """Handle webhook events."""
        data = event.data["data"]

        if not data.get("event_type"):
            return

        if not data.get("home"):
            return

        home = data["home"]
        if self._home_id == home["id"] and data["event_type"] == "therm_mode":
            self._preset = NETATMO_MAP_PRESET[home["therm_mode"]]
            self._hvac_mode = HVAC_MAP_NETATMO[self._preset]
            if self._preset == PRESET_FROST_GUARD:
                self._target_temperature = self._hg_temperature
            elif self._preset == PRESET_AWAY:
                self._target_temperature = self._away_temperature
            elif self._preset == PRESET_SCHEDULE:
                self.async_update_callback()
            self.async_write_ha_state()
            return

        if not home.get("rooms"):
            return

        for room in home["rooms"]:
            if data["event_type"] == "set_point":
                if self._id == room["id"]:
                    if room["therm_setpoint_mode"] == STATE_NETATMO_OFF:
                        self._hvac_mode = HVAC_MODE_OFF
                    elif room["therm_setpoint_mode"] == STATE_NETATMO_MAX:
                        self._hvac_mode = HVAC_MODE_HEAT
                        self._target_temperature = DEFAULT_MAX_TEMP
                    else:
                        self._target_temperature = room["therm_setpoint_temperature"]
                    self.async_write_ha_state()
                    break

            elif data["event_type"] == "cancel_set_point":
                if self._id == room["id"]:
                    self.async_update_callback()
                    self.async_write_ha_state()
                    break

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._support_flags

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
        if self._model == NA_THERM:
            return CURRENT_HVAC_MAP_NETATMO[self._boilerstatus]
        # Maybe it is a valve
        if self._room_status and self._room_status.get("heating_power_request", 0) > 0:
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
            self._home_status.set_room_thermpoint(
                self._id, STATE_NETATMO_HOME,
            )

        if preset_mode in [PRESET_BOOST, STATE_NETATMO_MAX] and self._model == NA_VALVE:
            self._home_status.set_room_thermpoint(
                self._id, STATE_NETATMO_MANUAL, DEFAULT_MAX_TEMP,
            )
        elif preset_mode in [PRESET_BOOST, STATE_NETATMO_MAX]:
            self._home_status.set_room_thermpoint(
                self._id, PRESET_MAP_NETATMO[preset_mode]
            )
        elif preset_mode in [PRESET_SCHEDULE, PRESET_FROST_GUARD, PRESET_AWAY]:
            self._home_status.set_thermmode(PRESET_MAP_NETATMO[preset_mode])
        else:
            _LOGGER.error("Preset mode '%s' not available", preset_mode)

        self.async_write_ha_state()

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
        self._home_status.set_room_thermpoint(self._id, STATE_NETATMO_MANUAL, temp)

        self.async_write_ha_state()

    @property
    def device_state_attributes(self):
        """Return the state attributes of the thermostat."""
        attr = {}

        if self._battery_level is not None:
            attr[ATTR_BATTERY_LEVEL] = self._battery_level

        if self._model == NA_VALVE:
            attr[ATTR_HEATING_POWER_REQUEST] = self._room_status.get(
                "heating_power_request", 0
            )

        return attr

    def turn_off(self):
        """Turn the entity off."""
        if self._model == NA_VALVE:
            self._home_status.set_room_thermpoint(
                self._id, STATE_NETATMO_MANUAL, DEFAULT_MIN_TEMP,
            )
        elif self.hvac_mode != HVAC_MODE_OFF:
            self._home_status.set_room_thermpoint(self._id, STATE_NETATMO_OFF)
        self.async_write_ha_state()

    def turn_on(self):
        """Turn the entity on."""
        self._home_status.set_room_thermpoint(self._id, STATE_NETATMO_HOME)
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """If the device hasn't been able to connect, mark as unavailable."""
        return bool(self._connected)

    @callback
    def async_update_callback(self):
        """Update the entity's state."""
        self._home_status = self.data_handler.data[self._home_status_class]
        self._room_status = self._home_status.rooms[self._id]
        self._room_data = self._data.rooms[self._home_id][self._id]

        roomstatus = {"roomID": self._room_status["id"]}
        if self._room_status.get("reachable"):
            roomstatus.update(self._build_room_status())

        self._away_temperature = self._data.get_away_temp(self._home_id)
        self._hg_temperature = self._data.get_hg_temp(self._home_id)
        self._setpoint_duration = self._data.setpoint_duration[self._home_id]

        try:
            if self._model is None:
                self._model = roomstatus["module_type"]
            self._current_temperature = roomstatus["current_temperature"]
            self._target_temperature = roomstatus["target_temperature"]
            self._preset = NETATMO_MAP_PRESET[roomstatus["setpoint_mode"]]
            self._hvac_mode = HVAC_MAP_NETATMO[self._preset]
            self._battery_level = roomstatus.get("battery_level")
            self._connected = True

        except KeyError as err:
            if self._connected:
                _LOGGER.debug(
                    "The thermostat in room %s seems to be out of reach. (%s)",
                    self._device_name,
                    err,
                )

            self._connected = False

        self._away = self._hvac_mode == HVAC_MAP_NETATMO[STATE_NETATMO_AWAY]

    def _build_room_status(self):
        """Construct room status."""
        try:
            roomstatus = {
                "roomname": self._room_data["name"],
                "target_temperature": self._room_status["therm_setpoint_temperature"],
                "setpoint_mode": self._room_status["therm_setpoint_mode"],
                "current_temperature": self._room_status["therm_measured_temperature"],
                "module_type": self._data.get_thermostat_type(
                    home_id=self._home_id, room_id=self._id
                ),
                "module_id": None,
                "heating_status": None,
                "heating_power_request": None,
            }

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
                roomstatus["heating_status"] = roomstatus["heating_power_request"] > 0
                if self._boilerstatus is not None:
                    roomstatus["heating_status"] = (
                        self._boilerstatus and roomstatus["heating_status"]
                    )
                batterylevel = self._home_status.valves[roomstatus["module_id"]].get(
                    "battery_level"
                )

            if batterylevel:
                batterypct = interpolate(batterylevel, roomstatus["module_type"])
                if (
                    not roomstatus.get("battery_level")
                    or batterypct < roomstatus["battery_level"]
                ):
                    roomstatus["battery_level"] = batterypct

            return roomstatus

        except KeyError as err:
            _LOGGER.error("Update of room %s failed. Error: %s", self._id, err)

        return {}

    def _service_setschedule(self, **kwargs):
        schedule_name = kwargs.get(ATTR_SCHEDULE_NAME)
        schedule_id = None
        for sid, name in self.hass.data[DOMAIN][DATA_SCHEDULES][self._home_id].items():
            if name == schedule_name:
                schedule_id = sid

        if not schedule_id:
            _LOGGER.error("You passed an invalid schedule")
            return

        self._data.switch_home_schedule(home_id=self._home_id, schedule_id=schedule_id)
        _LOGGER.info(
            "Setting %s schedule to %s (%s)",
            self._home_id,
            kwargs.get(ATTR_SCHEDULE_NAME),
            schedule_id,
        )


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


def get_all_home_ids(home_data):
    """Get all the home ids returned by NetAtmo API."""
    if home_data is None:
        return []
    return [
        home_data.homes[home_id]["id"]
        for home_id in home_data.homes
        if (
            "therm_schedules" in home_data.homes[home_id]
            and "modules" in home_data.homes[home_id]
        )
    ]
