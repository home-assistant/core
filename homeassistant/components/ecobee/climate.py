"""Support for ecobee thermostats."""
import collections

from pyecobee.const import ECOBEE_MODEL_TO_NAME
import voluptuous as vol

from homeassistant.components.climate import ClimateDevice
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
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
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
    STATE_OFF,
    STATE_ON,
    TEMP_FAHRENHEIT,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.util.temperature import convert

from .const import (
    _LOGGER,
    ATTR_COOL_TEMP,
    ATTR_END_DATE,
    ATTR_END_TIME,
    ATTR_FAN_MIN_ON_TIME,
    ATTR_FAN_MODE,
    ATTR_HEAT_TEMP,
    ATTR_RESUME_ALL,
    ATTR_START_DATE,
    ATTR_START_TIME,
    ATTR_VACATION_NAME,
    DEFAULT_RESUME_ALL,
    DOMAIN,
    MANUFACTURER,
    PRESET_HOLD_INDEFINITE,
    PRESET_HOLD_NEXT_TRANSITION,
    PRESET_TEMPERATURE,
    PRESET_VACATION,
)
from .util import ecobee_date, ecobee_time

# Order matters, because for reverse mapping we don't want to map HEAT to AUX
ECOBEE_HVAC_TO_HASS = collections.OrderedDict(
    [
        ("heat", HVAC_MODE_HEAT),
        ("cool", HVAC_MODE_COOL),
        ("auto", HVAC_MODE_AUTO),
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


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Old way of setting up ecobee thermostat."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up all ecobee thermostats."""

    data = hass.data[DOMAIN]

    devices = [Thermostat(data, index) for index in range(len(data.ecobee.thermostats))]

    async_add_entities(devices, True)

    async def create_vacation_service(service):
        """Create a vacation on the target thermostat."""
        entity_id = service.data[ATTR_ENTITY_ID]

        for thermostat in devices:
            if thermostat.entity_id == entity_id:
                await thermostat.create_vacation(service.data)
                thermostat.async_schedule_update_ha_state(True)
                break

    async def delete_vacation_service(service):
        """Delete a vacation on the target thermostat."""
        entity_id = service.data[ATTR_ENTITY_ID]
        vacation_name = service.data[ATTR_VACATION_NAME]

        for thermostat in devices:
            if thermostat.entity_id == entity_id:
                await thermostat.delete_vacation(vacation_name)
                thermostat.async_schedule_update_ha_state(True)
                break

    async def fan_min_on_time_set_service(service):
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
            await thermostat.set_fan_min_on_time(str(fan_min_on_time))
            thermostat.async_schedule_update_ha_state(True)

    async def resume_program_set_service(service):
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
            await thermostat.resume_program(resume_all=resume_all)
            thermostat.async_schedule_update_ha_state(True)

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


class Thermostat(ClimateDevice):
    """Thermostat class for ecobee."""

    def __init__(self, data, index):
        """Initialize the ecobee thermostat."""
        self._data = data
        self._index = index
        self._thermostat = self._data.ecobee.get_thermostat(self._index)
        self._operation_modes = self._create_operation_modes()
        self._preset_modes = self._create_preset_modes()
        self._last_active_hvac_mode = HVAC_MODE_AUTO
        self._vacation = None
        self._update_without_throttle = False

    def _create_operation_modes(self) -> list:
        """Create the operation modes for the thermostat; called in init."""
        operation_modes = []
        if self._thermostat["settings"]["heatStages"]:
            operation_modes.append(HVAC_MODE_HEAT)
        if self._thermostat["settings"]["coolStages"]:
            operation_modes.append(HVAC_MODE_COOL)
        if len(operation_modes) == 2:
            operation_modes.insert(0, HVAC_MODE_AUTO)
        operation_modes.append(HVAC_MODE_OFF)
        return operation_modes

    def _create_preset_modes(self) -> dict:
        """Create the preset modes for the thermostat; called in init."""
        preset_modes = {}
        for comfort in self._thermostat["program"]["climates"]:
            preset_modes[comfort["climateRef"]] = comfort["name"]
        return preset_modes

    @property
    def available(self):
        """Return if the thermostat is available."""
        return self._thermostat["runtime"]["connected"]

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def name(self):
        """Return the name of the thermostat."""
        return self._thermostat["name"]

    @property
    def unique_id(self):
        """Return a unique identifier for the thermostat."""
        return self._thermostat["identifier"]

    @property
    def device_info(self):
        """Return device information for the thermostat."""
        try:
            model = (
                f"{ECOBEE_MODEL_TO_NAME[self._thermostat['modelNumber']]} Thermostat"
            )
        except KeyError:
            _LOGGER.error(
                "Model number for ecobee thermostat %s not recognized. "
                "Please visit this link and provide the following information: "
                "https://github.com/home-assistant/home-assistant/issues/27172 "
                "Unrecognized model number: %s",
                self.name,
                self._thermostat["modelNumber"],
            )
            return None

        return {
            "identifiers": {(DOMAIN, self._thermostat["identifier"])},
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
        return self._thermostat["runtime"]["actualTemperature"] / 10.0

    @property
    def target_temperature_low(self):
        """Return the lower bound temperature we try to reach."""
        if self.hvac_mode == HVAC_MODE_AUTO:
            return self._thermostat["runtime"]["desiredHeat"] / 10.0
        return None

    @property
    def target_temperature_high(self):
        """Return the upper bound temperature we try to reach."""
        if self.hvac_mode == HVAC_MODE_AUTO:
            return self._thermostat["runtime"]["desiredCool"] / 10.0
        return None

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        if self.hvac_mode == HVAC_MODE_AUTO:
            return None
        if self.hvac_mode == HVAC_MODE_HEAT:
            return self._thermostat["runtime"]["desiredHeat"] / 10.0
        if self.hvac_mode == HVAC_MODE_COOL:
            return self._thermostat["runtime"]["desiredCool"] / 10.0
        return None

    @property
    def fan(self):
        """Return the current fan status."""
        if "fan" in self._thermostat["equipmentStatus"]:
            return STATE_ON
        return STATE_OFF

    @property
    def fan_mode(self):
        """Return the fan setting."""
        return self._thermostat["runtime"]["desiredFanMode"]

    @property
    def fan_modes(self):
        """Return the available fan modes."""
        return [FAN_AUTO, FAN_ON]

    @property
    def preset_mode(self):
        """Return the current preset mode."""
        events = self._thermostat["events"]
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
                self._vacation = event["name"]
                return PRESET_VACATION

        return self._preset_modes[self._thermostat["program"]["currentClimateRef"]]

    @property
    def preset_modes(self):
        """Return the available preset modes."""
        return list(self._preset_modes.values())

    @property
    def hvac_mode(self):
        """Return the current operation mode."""
        return ECOBEE_HVAC_TO_HASS[self._thermostat["settings"]["hvacMode"]]

    @property
    def hvac_modes(self):
        """Return the list of operation modes."""
        return self._operation_modes

    @property
    def current_humidity(self):
        """Return the current humidity."""
        return self._thermostat["runtime"]["actualHumidity"]

    @property
    def hvac_action(self):
        """Return the current HVAC action."""
        # Ecobee returns a CSV string with different equipment that is active.
        # We are prioritizing any heating/cooling equipment, otherwise look at
        # drying/fanning. Idle if nothing going on.
        # We are unable to map all actions to HA equivalents.
        if self._thermostat["equipmentStatus"] == "":
            return CURRENT_HVAC_IDLE

        actions = [
            ECOBEE_HVAC_ACTION_TO_HASS[status]
            for status in self._thermostat["equipmentStatus"].split(",")
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
        return {
            "fan": self.fan,
            "climate_mode": self._preset_modes[
                self._thermostat["program"]["currentClimateRef"]
            ],
            "equipment_running": self._thermostat["equipmentStatus"],
            "fan_min_on_time": self._thermostat["settings"]["fanMinOnTime"],
        }

    @property
    def is_aux_heat(self):
        """Return true if aux heater."""
        return "auxHeat" in self._thermostat["equipmentStatus"]

    async def async_set_preset_mode(self, preset_mode):
        """Activate a preset mode on the thermostat."""
        if preset_mode == self.preset_mode:
            return

        # If we are currently in vacation mode, cancel it.
        if self.preset_mode == PRESET_VACATION:
            await self.delete_vacation(self._vacation)

        if preset_mode == PRESET_AWAY:
            await self._data.request(
                self._data.ecobee.set_climate_hold, self._index, "away", "indefinite"
            )

        elif preset_mode == PRESET_TEMPERATURE:
            await self.set_temp_hold(self.current_temperature)

        elif preset_mode in (PRESET_HOLD_NEXT_TRANSITION, PRESET_HOLD_INDEFINITE):
            await self._data.request(
                self._data.ecobee.set_climate_hold,
                self._index,
                PRESET_TO_ECOBEE_HOLD[preset_mode],
                self.hold_preference(),
            )

        elif preset_mode == PRESET_NONE:
            await self.resume_program()

        elif preset_mode in self.preset_modes:
            climate_ref = None

            for comfort in self._thermostat["program"]["climates"]:
                if comfort["name"] == preset_mode:
                    climate_ref = comfort["climateRef"]
                    break

            if climate_ref is not None:
                await self._data.request(
                    self._data.ecobee.set_climate_hold,
                    self._index,
                    climate_ref,
                    self.hold_preference(),
                )
            else:
                _LOGGER.warning("Received unknown preset mode: %s", preset_mode)

        else:
            await self._data.request(
                self._data.ecobee.set_climate_hold,
                self._index,
                preset_mode,
                self.hold_preference(),
            )
        self._update_without_throttle = True

    async def async_set_fan_mode(self, fan_mode):
        """Set the fan mode. Valid values are "on" or "auto"."""
        if fan_mode.lower() != STATE_ON and fan_mode.lower() != HVAC_MODE_AUTO:
            _LOGGER.error("Invalid fan_mode value: valid values are 'on' or 'auto'")
            return

        cool_temp = self._thermostat["runtime"]["desiredCool"] / 10.0
        heat_temp = self._thermostat["runtime"]["desiredHeat"] / 10.0
        _LOGGER.debug("Setting fan mode on thermostat %s to %s", self.name, fan_mode)
        await self._data.request(
            self._data.ecobee.set_fan_mode,
            self._index,
            fan_mode,
            cool_temp,
            heat_temp,
            self.hold_preference(),
        )
        self._update_without_throttle = True

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        low_temp = kwargs.get(ATTR_TARGET_TEMP_LOW)
        high_temp = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        temp = kwargs.get(ATTR_TEMPERATURE)

        if self.hvac_mode == HVAC_MODE_AUTO and (
            low_temp is not None or high_temp is not None
        ):
            await self.set_auto_temp_hold(low_temp, high_temp)
        elif temp is not None:
            await self.set_temp_hold(temp)
        else:
            _LOGGER.error("Missing valid arguments for set_temperature in %s", kwargs)

    async def async_set_humidity(self, humidity):
        """Set the humidity level."""
        _LOGGER.debug(
            "Setting humidity level on thermostat %s to %s", self.name, humidity
        )
        await self._data.request(self._data.ecobee.set_humidity, self._index, humidity)
        self._update_without_throttle = True

    async def async_set_hvac_mode(self, hvac_mode):
        """Set HVAC mode (auto, auxHeatOnly, cool, heat, off)."""
        ecobee_value = next(
            (k for k, v in ECOBEE_HVAC_TO_HASS.items() if v == hvac_mode), None
        )
        if ecobee_value is None:
            _LOGGER.error("Invalid mode for async_set_hvac_mode: %s", hvac_mode)
            return
        _LOGGER.debug(
            "Setting HVAC mode on thermostat %s to %s", self.name, ecobee_value
        )
        await self._data.request(
            self._data.ecobee.set_hvac_mode, self._index, ecobee_value
        )
        self._update_without_throttle = True

    async def async_turn_on(self):
        """Set the thermostat to the last active HVAC mode."""
        _LOGGER.debug(
            "Turning on thermostat %s in %s mode",
            self.name,
            self._last_active_hvac_mode,
        )
        await self.async_set_hvac_mode(self._last_active_hvac_mode)
        self._update_without_throttle = True

    async def async_turn_off(self):
        """Turn the thermostat off."""
        _LOGGER.debug("Turning off thermostat %s", self.name)
        await self.async_set_hvac_mode(HVAC_MODE_OFF)
        self._update_without_throttle = True

    async def async_update(self):
        """Get the latest state data from ecobee."""
        if self._update_without_throttle:
            await self._data.update(no_throttle=True)
            self._update_without_throttle = False
        else:
            await self._data.update()
        self._thermostat = self._data.ecobee.get_thermostat(self._index)
        if self.hvac_mode is not HVAC_MODE_OFF:
            self._last_active_hvac_mode = self.hvac_mode

    async def set_auto_temp_hold(self, heat_temp, cool_temp):
        """Set temperature hold in auto mode."""
        cool_temp_setpoint = (
            cool_temp
            if cool_temp is not None
            else self._thermostat["runtime"]["desiredCool"] / 10.0
        )

        heat_temp_setpoint = (
            heat_temp
            if heat_temp is not None
            else self._thermostat["runtime"]["desiredCool"] / 10.0
        )

        _LOGGER.debug(
            "Setting hold temperature on thermostat %s to "
            "heat_temp: %s, cool_temp: %s",
            self.name,
            heat_temp_setpoint,
            cool_temp_setpoint,
        )
        await self._data.request(
            self._data.ecobee.set_hold_temp,
            self._index,
            cool_temp_setpoint,
            heat_temp_setpoint,
            self.hold_preference(),
        )
        self._update_without_throttle = True

    async def set_temp_hold(self, temp):
        """Set temperature hold in modes other than auto."""
        # Ecobee API: It is good practice to set the heat and cool hold
        # temperatures to be the same, if the thermostat is in either heat, cool,
        # auxHeatOnly, or off mode. If the thermostat is in auto mode, an
        # additional rule is required. The cool hold temperature must be greater
        # than the heat hold temperature by at least the amount in the
        # heatCoolMinDelta property.
        # https://www.ecobee.com/home/developer/api/examples/ex5.shtml
        if self.hvac_mode == HVAC_MODE_HEAT or self.hvac_mode == HVAC_MODE_COOL:
            heat_temp = temp
            cool_temp = temp
        else:
            delta = self._thermostat["settings"]["heatCoolMinDelta"] / 10
            heat_temp = temp - delta
            cool_temp = temp + delta
        await self.set_auto_temp_hold(heat_temp, cool_temp)

    async def set_fan_min_on_time(self, fan_min_on_time):
        """Set the minimum fan on time."""
        _LOGGER.debug(
            "Setting minimum fan on time on thermostat %s to %s",
            self.name,
            fan_min_on_time,
        )
        await self._data.request(
            self._data.ecobee.set_fan_min_on_time, self._index, fan_min_on_time
        )
        self._update_without_throttle = True

    async def resume_program(self, resume_all: bool = False):
        """Resume the scheduled thermostat program."""
        _LOGGER.debug(
            "Resuming the program on thermostat %s with resume_all %",
            self.name,
            resume_all,
        )
        await self._data.request(
            self._data.ecobee.resume_program,
            self._index,
            "true" if resume_all else "false",
        )
        self._update_without_throttle = True

    def hold_preference(self):
        """Return user preference setting for hold time."""
        # Values returned from thermostat are 'useEndTime4hour',
        # 'useEndTime2hour', 'nextTransition', 'indefinite', 'askMe'
        default = self._thermostat["settings"]["holdAction"]
        if default == "nextTransition":
            return default
        # add further conditions if other hold durations should be
        # supported; note that this should not include 'indefinite'
        # as an indefinite away hold is interpreted as away_mode
        return "nextTransition"

    async def create_vacation(self, service_data):
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
            "Creating a vacation on thermostat %s with name %s, "
            "cool temp %s, heat temp %s, "
            "and the following other parameters: %s",
            self.name,
            vacation_name,
            cool_temp,
            heat_temp,
            kwargs,
        )
        await self._data.request(
            self._data.ecobee.create_vacation,
            self._index,
            vacation_name,
            cool_temp,
            heat_temp,
            **kwargs,
        )
        self._update_without_throttle = True

    async def delete_vacation(self, vacation_name):
        """Delete a vacation with the specified name."""
        _LOGGER.debug(
            "Deleting a vacation on thermostat %s with name %s",
            self.name,
            vacation_name,
        )
        await self._data.request(
            self._data.ecobee.delete_vacation, self._index, vacation_name
        )
        self._update_without_throttle = True
