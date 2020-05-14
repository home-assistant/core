"""Support for Ecobee Thermostats."""
import collections
from typing import Optional

import voluptuous as vol

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_DRY,
    CURRENT_HVAC_FAN,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    FAN_AUTO,
    FAN_ON,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_OFF,
    PRESET_AWAY,
    PRESET_NONE,
    SUPPORT_AUX_HEAT,
    SUPPORT_FAN_MODE,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_TARGET_TEMPERATURE_RANGE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    STATE_ON,
    TEMP_FAHRENHEIT,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.util.temperature import convert

from .const import _LOGGER, DOMAIN, ECOBEE_MODEL_TO_NAME, MANUFACTURER
from .util import ecobee_date, ecobee_time

ATTR_COOL_TEMP = "cool_temp"
ATTR_END_DATE = "end_date"
ATTR_END_TIME = "end_time"
ATTR_FAN_MIN_ON_TIME = "fan_min_on_time"
ATTR_FAN_MODE = "fan_mode"
ATTR_HEAT_TEMP = "heat_temp"
ATTR_RESUME_ALL = "resume_all"
ATTR_START_DATE = "start_date"
ATTR_START_TIME = "start_time"
ATTR_VACATION_NAME = "vacation_name"

DEFAULT_RESUME_ALL = False
PRESET_TEMPERATURE = "temp"
PRESET_VACATION = "vacation"
PRESET_HOLD_NEXT_TRANSITION = "next_transition"
PRESET_HOLD_INDEFINITE = "indefinite"
AWAY_MODE = "awayMode"
PRESET_HOME = "home"
PRESET_SLEEP = "sleep"

# Order matters, because for reverse mapping we don't want to map HEAT to AUX
ECOBEE_HVAC_TO_HASS = collections.OrderedDict(
    [
        ("heat", HVAC_MODE_HEAT),
        ("cool", HVAC_MODE_COOL),
        ("auto", HVAC_MODE_HEAT_COOL),
        ("off", HVAC_MODE_OFF),
        ("auxHeatOnly", HVAC_MODE_HEAT),
    ]
)

ECOBEE_HVAC_ACTION_TO_HASS = {
    # Map to None if we do not know how to represent.
    "heatPump": CURRENT_HVAC_HEAT,
    "heatPump2": CURRENT_HVAC_HEAT,
    "heatPump3": CURRENT_HVAC_HEAT,
    "compCool1": CURRENT_HVAC_COOL,
    "compCool2": CURRENT_HVAC_COOL,
    "auxHeat1": CURRENT_HVAC_HEAT,
    "auxHeat2": CURRENT_HVAC_HEAT,
    "auxHeat3": CURRENT_HVAC_HEAT,
    "fan": CURRENT_HVAC_FAN,
    "humidifier": None,
    "dehumidifier": CURRENT_HVAC_DRY,
    "ventilator": CURRENT_HVAC_FAN,
    "economizer": CURRENT_HVAC_FAN,
    "compHotWater": None,
    "auxHotWater": None,
}

PRESET_TO_ECOBEE_HOLD = {
    PRESET_HOLD_NEXT_TRANSITION: "nextTransition",
    PRESET_HOLD_INDEFINITE: "indefinite",
}

SERVICE_CREATE_VACATION = "create_vacation"
SERVICE_DELETE_VACATION = "delete_vacation"
SERVICE_RESUME_PROGRAM = "resume_program"
SERVICE_SET_FAN_MIN_ON_TIME = "set_fan_min_on_time"

DTGROUP_INCLUSIVE_MSG = (
    f"{ATTR_START_DATE}, {ATTR_START_TIME}, {ATTR_END_DATE}, "
    f"and {ATTR_END_TIME} must be specified together"
)

CREATE_VACATION_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_VACATION_NAME): vol.All(cv.string, vol.Length(max=12)),
        vol.Required(ATTR_COOL_TEMP): vol.Coerce(float),
        vol.Required(ATTR_HEAT_TEMP): vol.Coerce(float),
        vol.Inclusive(
            ATTR_START_DATE, "dtgroup", msg=DTGROUP_INCLUSIVE_MSG
        ): ecobee_date,
        vol.Inclusive(
            ATTR_START_TIME, "dtgroup", msg=DTGROUP_INCLUSIVE_MSG
        ): ecobee_time,
        vol.Inclusive(ATTR_END_DATE, "dtgroup", msg=DTGROUP_INCLUSIVE_MSG): ecobee_date,
        vol.Inclusive(ATTR_END_TIME, "dtgroup", msg=DTGROUP_INCLUSIVE_MSG): ecobee_time,
        vol.Optional(ATTR_FAN_MODE, default="auto"): vol.Any("auto", "on"),
        vol.Optional(ATTR_FAN_MIN_ON_TIME, default=0): vol.All(
            int, vol.Range(min=0, max=60)
        ),
    }
)

DELETE_VACATION_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_VACATION_NAME): vol.All(cv.string, vol.Length(max=12)),
    }
)

RESUME_PROGRAM_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Optional(ATTR_RESUME_ALL, default=DEFAULT_RESUME_ALL): cv.boolean,
    }
)

SET_FAN_MIN_ON_TIME_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Required(ATTR_FAN_MIN_ON_TIME): vol.Coerce(int),
    }
)


SUPPORT_FLAGS = (
    SUPPORT_TARGET_TEMPERATURE
    | SUPPORT_PRESET_MODE
    | SUPPORT_AUX_HEAT
    | SUPPORT_TARGET_TEMPERATURE_RANGE
    | SUPPORT_FAN_MODE
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the ecobee thermostat."""

    data = hass.data[DOMAIN]

    devices = [Thermostat(data, index) for index in range(len(data.ecobee.thermostats))]

    async_add_entities(devices, True)

    def create_vacation_service(service):
        """Create a vacation on the target thermostat."""
        entity_id = service.data[ATTR_ENTITY_ID]

        for thermostat in devices:
            if thermostat.entity_id == entity_id:
                thermostat.create_vacation(service.data)
                thermostat.schedule_update_ha_state(True)
                break

    def delete_vacation_service(service):
        """Delete a vacation on the target thermostat."""
        entity_id = service.data[ATTR_ENTITY_ID]
        vacation_name = service.data[ATTR_VACATION_NAME]

        for thermostat in devices:
            if thermostat.entity_id == entity_id:
                thermostat.delete_vacation(vacation_name)
                thermostat.schedule_update_ha_state(True)
                break

    def fan_min_on_time_set_service(service):
        """Set the minimum fan on time on the target thermostats."""
        entity_id = service.data.get(ATTR_ENTITY_ID)
        fan_min_on_time = service.data[ATTR_FAN_MIN_ON_TIME]

        if entity_id:
            target_thermostats = [
                device for device in devices if device.entity_id in entity_id
            ]
        else:
            target_thermostats = devices

        for thermostat in target_thermostats:
            thermostat.set_fan_min_on_time(str(fan_min_on_time))

            thermostat.schedule_update_ha_state(True)

    def resume_program_set_service(service):
        """Resume the program on the target thermostats."""
        entity_id = service.data.get(ATTR_ENTITY_ID)
        resume_all = service.data.get(ATTR_RESUME_ALL)

        if entity_id:
            target_thermostats = [
                device for device in devices if device.entity_id in entity_id
            ]
        else:
            target_thermostats = devices

        for thermostat in target_thermostats:
            thermostat.resume_program(resume_all)

            thermostat.schedule_update_ha_state(True)

    hass.services.async_register(
        DOMAIN,
        SERVICE_CREATE_VACATION,
        create_vacation_service,
        schema=CREATE_VACATION_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_DELETE_VACATION,
        delete_vacation_service,
        schema=DELETE_VACATION_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_FAN_MIN_ON_TIME,
        fan_min_on_time_set_service,
        schema=SET_FAN_MIN_ON_TIME_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_RESUME_PROGRAM,
        resume_program_set_service,
        schema=RESUME_PROGRAM_SCHEMA,
    )


class Thermostat(ClimateEntity):
    """A thermostat class for Ecobee."""

    def __init__(self, data, thermostat_index):
        """Initialize the thermostat."""
        self.data = data
        self.thermostat_index = thermostat_index
        self.thermostat = self.data.ecobee.get_thermostat(self.thermostat_index)
        self._name = self.thermostat["name"]
        self.vacation = None
        self._last_active_hvac_mode = HVAC_MODE_HEAT_COOL

        self._operation_list = []
        if (
            self.thermostat["settings"]["heatStages"]
            or self.thermostat["settings"]["hasHeatPump"]
        ):
            self._operation_list.append(HVAC_MODE_HEAT)
        if self.thermostat["settings"]["coolStages"]:
            self._operation_list.append(HVAC_MODE_COOL)
        if len(self._operation_list) == 2:
            self._operation_list.insert(0, HVAC_MODE_HEAT_COOL)
        self._operation_list.append(HVAC_MODE_OFF)

        self._preset_modes = {
            comfort["climateRef"]: comfort["name"]
            for comfort in self.thermostat["program"]["climates"]
        }
        self._fan_modes = [FAN_AUTO, FAN_ON]
        self.update_without_throttle = False

    async def async_update(self):
        """Get the latest state from the thermostat."""
        if self.update_without_throttle:
            await self.data.update(no_throttle=True)
            self.update_without_throttle = False
        else:
            await self.data.update()
        self.thermostat = self.data.ecobee.get_thermostat(self.thermostat_index)
        if self.hvac_mode != HVAC_MODE_OFF:
            self._last_active_hvac_mode = self.hvac_mode

    @property
    def available(self):
        """Return if device is available."""
        return self.thermostat["runtime"]["connected"]

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def name(self):
        """Return the name of the Ecobee Thermostat."""
        return self.thermostat["name"]

    @property
    def unique_id(self):
        """Return a unique identifier for this ecobee thermostat."""
        return self.thermostat["identifier"]

    @property
    def device_info(self):
        """Return device information for this ecobee thermostat."""
        try:
            model = f"{ECOBEE_MODEL_TO_NAME[self.thermostat['modelNumber']]} Thermostat"
        except KeyError:
            _LOGGER.error(
                "Model number for ecobee thermostat %s not recognized. "
                "Please visit this link and provide the following information: "
                "https://github.com/home-assistant/home-assistant/issues/27172 "
                "Unrecognized model number: %s",
                self.name,
                self.thermostat["modelNumber"],
            )
            return None

        return {
            "identifiers": {(DOMAIN, self.thermostat["identifier"])},
            "name": self.name,
            "manufacturer": MANUFACTURER,
            "model": model,
        }

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_FAHRENHEIT

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self.thermostat["runtime"]["actualTemperature"] / 10.0

    @property
    def target_temperature_low(self):
        """Return the lower bound temperature we try to reach."""
        if self.hvac_mode == HVAC_MODE_HEAT_COOL:
            return self.thermostat["runtime"]["desiredHeat"] / 10.0
        return None

    @property
    def target_temperature_high(self):
        """Return the upper bound temperature we try to reach."""
        if self.hvac_mode == HVAC_MODE_HEAT_COOL:
            return self.thermostat["runtime"]["desiredCool"] / 10.0
        return None

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        if self.hvac_mode == HVAC_MODE_HEAT_COOL:
            return None
        if self.hvac_mode == HVAC_MODE_HEAT:
            return self.thermostat["runtime"]["desiredHeat"] / 10.0
        if self.hvac_mode == HVAC_MODE_COOL:
            return self.thermostat["runtime"]["desiredCool"] / 10.0
        return None

    @property
    def fan(self):
        """Return the current fan status."""
        if "fan" in self.thermostat["equipmentStatus"]:
            return STATE_ON
        return HVAC_MODE_OFF

    @property
    def fan_mode(self):
        """Return the fan setting."""
        return self.thermostat["runtime"]["desiredFanMode"]

    @property
    def fan_modes(self):
        """Return the available fan modes."""
        return self._fan_modes

    @property
    def preset_mode(self):
        """Return current preset mode."""
        events = self.thermostat["events"]
        for event in events:
            if not event["running"]:
                continue

            if event["type"] == "hold":
                if event["holdClimateRef"] in self._preset_modes:
                    return self._preset_modes[event["holdClimateRef"]]

                # Any hold not based on a climate is a temp hold
                return PRESET_TEMPERATURE
            if event["type"].startswith("auto"):
                # All auto modes are treated as holds
                return event["type"][4:].lower()
            if event["type"] == "vacation":
                self.vacation = event["name"]
                return PRESET_VACATION

        return self._preset_modes[self.thermostat["program"]["currentClimateRef"]]

    @property
    def hvac_mode(self):
        """Return current operation."""
        return ECOBEE_HVAC_TO_HASS[self.thermostat["settings"]["hvacMode"]]

    @property
    def hvac_modes(self):
        """Return the operation modes list."""
        return self._operation_list

    @property
    def current_humidity(self) -> Optional[int]:
        """Return the current humidity."""
        return self.thermostat["runtime"]["actualHumidity"]

    @property
    def hvac_action(self):
        """Return current HVAC action.

        Ecobee returns a CSV string with different equipment that is active.
        We are prioritizing any heating/cooling equipment, otherwase look at
        drying/fanning. Idle if nothing going on.

        We are unable to map all actions to HA equivalents.
        """
        if self.thermostat["equipmentStatus"] == "":
            return CURRENT_HVAC_IDLE

        actions = [
            ECOBEE_HVAC_ACTION_TO_HASS[status]
            for status in self.thermostat["equipmentStatus"].split(",")
            if ECOBEE_HVAC_ACTION_TO_HASS[status] is not None
        ]

        for action in (
            CURRENT_HVAC_HEAT,
            CURRENT_HVAC_COOL,
            CURRENT_HVAC_DRY,
            CURRENT_HVAC_FAN,
        ):
            if action in actions:
                return action

        return CURRENT_HVAC_IDLE

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        status = self.thermostat["equipmentStatus"]
        return {
            "fan": self.fan,
            "climate_mode": self._preset_modes[
                self.thermostat["program"]["currentClimateRef"]
            ],
            "equipment_running": status,
            "fan_min_on_time": self.thermostat["settings"]["fanMinOnTime"],
        }

    @property
    def is_aux_heat(self):
        """Return true if aux heater."""
        return "auxHeat" in self.thermostat["equipmentStatus"]

    def set_preset_mode(self, preset_mode):
        """Activate a preset."""
        if preset_mode == self.preset_mode:
            return

        self.update_without_throttle = True

        # If we are currently in vacation mode, cancel it.
        if self.preset_mode == PRESET_VACATION:
            self.data.ecobee.delete_vacation(self.thermostat_index, self.vacation)

        if preset_mode == PRESET_AWAY:
            self.data.ecobee.set_climate_hold(
                self.thermostat_index, "away", "indefinite"
            )

        elif preset_mode == PRESET_TEMPERATURE:
            self.set_temp_hold(self.current_temperature)

        elif preset_mode in (PRESET_HOLD_NEXT_TRANSITION, PRESET_HOLD_INDEFINITE):
            self.data.ecobee.set_climate_hold(
                self.thermostat_index,
                PRESET_TO_ECOBEE_HOLD[preset_mode],
                self.hold_preference(),
            )

        elif preset_mode == PRESET_NONE:
            self.data.ecobee.resume_program(self.thermostat_index)

        elif preset_mode in self.preset_modes:
            climate_ref = None

            for comfort in self.thermostat["program"]["climates"]:
                if comfort["name"] == preset_mode:
                    climate_ref = comfort["climateRef"]
                    break

            if climate_ref is not None:
                self.data.ecobee.set_climate_hold(
                    self.thermostat_index, climate_ref, self.hold_preference()
                )
            else:
                _LOGGER.warning("Received unknown preset mode: %s", preset_mode)

        else:
            self.data.ecobee.set_climate_hold(
                self.thermostat_index, preset_mode, self.hold_preference()
            )

    @property
    def preset_modes(self):
        """Return available preset modes."""
        return list(self._preset_modes.values())

    def set_auto_temp_hold(self, heat_temp, cool_temp):
        """Set temperature hold in auto mode."""
        if cool_temp is not None:
            cool_temp_setpoint = cool_temp
        else:
            cool_temp_setpoint = self.thermostat["runtime"]["desiredCool"] / 10.0

        if heat_temp is not None:
            heat_temp_setpoint = heat_temp
        else:
            heat_temp_setpoint = self.thermostat["runtime"]["desiredCool"] / 10.0

        self.data.ecobee.set_hold_temp(
            self.thermostat_index,
            cool_temp_setpoint,
            heat_temp_setpoint,
            self.hold_preference(),
        )
        _LOGGER.debug(
            "Setting ecobee hold_temp to: heat=%s, is=%s, cool=%s, is=%s",
            heat_temp,
            isinstance(heat_temp, (int, float)),
            cool_temp,
            isinstance(cool_temp, (int, float)),
        )

        self.update_without_throttle = True

    def set_fan_mode(self, fan_mode):
        """Set the fan mode.  Valid values are "on" or "auto"."""
        if fan_mode.lower() not in (FAN_ON, FAN_AUTO):
            error = "Invalid fan_mode value:  Valid values are 'on' or 'auto'"
            _LOGGER.error(error)
            return

        cool_temp = self.thermostat["runtime"]["desiredCool"] / 10.0
        heat_temp = self.thermostat["runtime"]["desiredHeat"] / 10.0
        self.data.ecobee.set_fan_mode(
            self.thermostat_index,
            fan_mode,
            cool_temp,
            heat_temp,
            self.hold_preference(),
        )

        _LOGGER.info("Setting fan mode to: %s", fan_mode)

    def set_temp_hold(self, temp):
        """Set temperature hold in modes other than auto.

        Ecobee API: It is good practice to set the heat and cool hold
        temperatures to be the same, if the thermostat is in either heat, cool,
        auxHeatOnly, or off mode. If the thermostat is in auto mode, an
        additional rule is required. The cool hold temperature must be greater
        than the heat hold temperature by at least the amount in the
        heatCoolMinDelta property.
        https://www.ecobee.com/home/developer/api/examples/ex5.shtml
        """
        if self.hvac_mode == HVAC_MODE_HEAT or self.hvac_mode == HVAC_MODE_COOL:
            heat_temp = temp
            cool_temp = temp
        else:
            delta = self.thermostat["settings"]["heatCoolMinDelta"] / 10
            heat_temp = temp - delta
            cool_temp = temp + delta
        self.set_auto_temp_hold(heat_temp, cool_temp)

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        low_temp = kwargs.get(ATTR_TARGET_TEMP_LOW)
        high_temp = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        temp = kwargs.get(ATTR_TEMPERATURE)

        if self.hvac_mode == HVAC_MODE_HEAT_COOL and (
            low_temp is not None or high_temp is not None
        ):
            self.set_auto_temp_hold(low_temp, high_temp)
        elif temp is not None:
            self.set_temp_hold(temp)
        else:
            _LOGGER.error("Missing valid arguments for set_temperature in %s", kwargs)

    def set_humidity(self, humidity):
        """Set the humidity level."""
        self.data.ecobee.set_humidity(self.thermostat_index, humidity)

    def set_hvac_mode(self, hvac_mode):
        """Set HVAC mode (auto, auxHeatOnly, cool, heat, off)."""
        ecobee_value = next(
            (k for k, v in ECOBEE_HVAC_TO_HASS.items() if v == hvac_mode), None
        )
        if ecobee_value is None:
            _LOGGER.error("Invalid mode for set_hvac_mode: %s", hvac_mode)
            return
        self.data.ecobee.set_hvac_mode(self.thermostat_index, ecobee_value)
        self.update_without_throttle = True

    def set_fan_min_on_time(self, fan_min_on_time):
        """Set the minimum fan on time."""
        self.data.ecobee.set_fan_min_on_time(self.thermostat_index, fan_min_on_time)
        self.update_without_throttle = True

    def resume_program(self, resume_all):
        """Resume the thermostat schedule program."""
        self.data.ecobee.resume_program(
            self.thermostat_index, "true" if resume_all else "false"
        )
        self.update_without_throttle = True

    def hold_preference(self):
        """Return user preference setting for hold time."""
        # Values returned from thermostat are 'useEndTime4hour',
        # 'useEndTime2hour', 'nextTransition', 'indefinite', 'askMe'
        default = self.thermostat["settings"]["holdAction"]
        if default == "nextTransition":
            return default
        # add further conditions if other hold durations should be
        # supported; note that this should not include 'indefinite'
        # as an indefinite away hold is interpreted as away_mode
        return "nextTransition"

    def create_vacation(self, service_data):
        """Create a vacation with user-specified parameters."""
        vacation_name = service_data[ATTR_VACATION_NAME]
        cool_temp = convert(
            service_data[ATTR_COOL_TEMP],
            self.hass.config.units.temperature_unit,
            TEMP_FAHRENHEIT,
        )
        heat_temp = convert(
            service_data[ATTR_HEAT_TEMP],
            self.hass.config.units.temperature_unit,
            TEMP_FAHRENHEIT,
        )
        start_date = service_data.get(ATTR_START_DATE)
        start_time = service_data.get(ATTR_START_TIME)
        end_date = service_data.get(ATTR_END_DATE)
        end_time = service_data.get(ATTR_END_TIME)
        fan_mode = service_data[ATTR_FAN_MODE]
        fan_min_on_time = service_data[ATTR_FAN_MIN_ON_TIME]

        kwargs = {
            key: value
            for key, value in {
                "start_date": start_date,
                "start_time": start_time,
                "end_date": end_date,
                "end_time": end_time,
                "fan_mode": fan_mode,
                "fan_min_on_time": fan_min_on_time,
            }.items()
            if value is not None
        }

        _LOGGER.debug(
            "Creating a vacation on thermostat %s with name %s, cool temp %s, heat temp %s, "
            "and the following other parameters: %s",
            self.name,
            vacation_name,
            cool_temp,
            heat_temp,
            kwargs,
        )
        self.data.ecobee.create_vacation(
            self.thermostat_index, vacation_name, cool_temp, heat_temp, **kwargs
        )

    def delete_vacation(self, vacation_name):
        """Delete a vacation with the specified name."""
        _LOGGER.debug(
            "Deleting a vacation on thermostat %s with name %s",
            self.name,
            vacation_name,
        )
        self.data.ecobee.delete_vacation(self.thermostat_index, vacation_name)

    def turn_on(self):
        """Set the thermostat to the last active HVAC mode."""
        _LOGGER.debug(
            "Turning on ecobee thermostat %s in %s mode",
            self.name,
            self._last_active_hvac_mode,
        )
        self.set_hvac_mode(self._last_active_hvac_mode)
