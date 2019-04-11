"""
Support for Honeywell Lyric thermostats.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/lyric
"""
import logging

import voluptuous as vol

from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateDevice
from homeassistant.components.climate.const import (
    ATTR_TARGET_TEMP_HIGH, ATTR_TARGET_TEMP_LOW, STATE_AUTO, STATE_COOL,
    STATE_HEAT, SUPPORT_OPERATION_MODE, SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_TARGET_TEMPERATURE_HIGH, SUPPORT_TARGET_TEMPERATURE_LOW)
from homeassistant.components.lyric import DATA_LYRIC, DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_TEMPERATURE, ATTR_TIME, CONF_SCAN_INTERVAL, STATE_OFF,
    STATE_UNKNOWN, TEMP_CELSIUS, TEMP_FAHRENHEIT)
import homeassistant.helpers.config_validation as cv

DEPENDENCIES = ['lyric']

_LOGGER = logging.getLogger(__name__)

SERVICE_RESUME_PROGRAM = 'resume_program'
SERVICE_HOLD_TIME = 'set_hold_time'
STATE_HEAT_COOL = 'heat-cool'
HOLD_NO_HOLD = 'NoHold'

SUPPORT_FLAGS = (SUPPORT_TARGET_TEMPERATURE | SUPPORT_TARGET_TEMPERATURE_HIGH |
                 SUPPORT_TARGET_TEMPERATURE_LOW | SUPPORT_OPERATION_MODE)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_SCAN_INTERVAL):
        vol.All(vol.Coerce(int), vol.Range(min=1))
})

RESUME_PROGRAM_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids
})

HOLD_PERIOD_SCHEMA = vol.Schema({
    vol.Required(ATTR_TIME): cv.string,
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Lyric thermostat."""
    if discovery_info is None:
        return

    _LOGGER.debug("Climate discovery_info: %s", discovery_info)
    _LOGGER.debug("Climate config: %s", config)

    temp_unit = hass.config.units.temperature_unit

    _LOGGER.debug('Set up Lyric climate platform')

    devices = [LyricThermostat(location, device, hass, temp_unit)
               for location, device in hass.data[DATA_LYRIC].thermostats()]

    add_devices(devices, True)

    def resume_program_service(service):
        """Resume the program on the target thermostats."""
        entity_id = service.data.get(ATTR_ENTITY_ID)

        _LOGGER.debug('resume_program_service entity_id: %s', entity_id)

        if entity_id:
            target_thermostats = [device for device in devices
                                  if device.entity_id in entity_id]
        else:
            target_thermostats = devices

        for thermostat in target_thermostats:
            thermostat.set_hold_mode(HOLD_NO_HOLD)

    def hold_time_service(service):
        """Set the time to hold until."""
        entity_id = service.data.get(ATTR_ENTITY_ID)
        time = service.data.get(ATTR_TIME)

        _LOGGER.debug('hold_time_service entity_id: %s', entity_id)
        _LOGGER.debug('hold_time_service time: %s', time)

        if entity_id:
            target_thermostats = [device for device in devices
                                  if device.entity_id in entity_id]
        else:
            target_thermostats = devices

        for thermostat in target_thermostats:
            thermostat.set_hold_period(time)

    hass.services.register(
        DOMAIN, SERVICE_RESUME_PROGRAM, resume_program_service,
        schema=RESUME_PROGRAM_SCHEMA)

    hass.services.register(
        DOMAIN, SERVICE_HOLD_TIME, hold_time_service,
        schema=HOLD_PERIOD_SCHEMA)


class LyricThermostat(ClimateDevice):
    """Representation of a Lyric thermostat."""

    def __init__(self, location, device, hass, temp_unit):
        """Initialize the thermostat."""
        self._unique_id = '{}_climate'.format(device.macID)
        self._unit = temp_unit
        self.location = location
        self.device = device
        self._hass = hass

        # Not all lyric devices support cooling and heating remove unused
        self._operation_list = [STATE_OFF]

        # Add supported lyric thermostat features
        if self.device.can_heat:
            self._operation_list.append(STATE_HEAT)

        if self.device.can_cool:
            self._operation_list.append(STATE_COOL)

        if self.device.can_heat and self.device.can_cool:
            self._operation_list.append(STATE_AUTO)

        # data attributes
        self._location = None
        self._name = None
        self._humidity = None
        self._target_temperature = None
        self._setpoint_status = None
        self._temperature = None
        self._temperature_scale = None
        self._target_temp_heat = None
        self._target_temp_cool = None
        self._dual_setpoint = None
        self._mode = None
        self._min_temperature = None
        self._max_temperature = None
        self._schedule_type = None
        self._schedule_sub_type = None
        self._current_schedule_period = None
        self._current_schedule_period_day = None
        self._vacation_hold = None

    @property
    def name(self):
        """Return the name of the lyric, if any."""
        return self._name

    @property
    def unique_id(self):
        """Return unique ID for the thermostat."""
        return self._unique_id

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._temperature_scale

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._temperature

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        if self._mode in [STATE_HEAT, STATE_COOL, STATE_OFF]:
            return self._mode
        elif self._mode == STATE_HEAT_COOL:
            return STATE_AUTO
        else:
            return STATE_UNKNOWN

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        if not self._dual_setpoint:
            return self._target_temperature
        else:
            return None

    @property
    def target_temperature_low(self):
        """Return the upper bound temperature we try to reach."""
        if self._dual_setpoint:
            return self._target_temp_cool
        else:
            return None

    @property
    def target_temperature_high(self):
        """Return the upper bound temperature we try to reach."""
        if self._dual_setpoint:
            return self._target_temp_heat
        else:
            return None

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        target_temp_low = kwargs.get(ATTR_TARGET_TEMP_LOW)
        target_temp_high = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        if self._dual_setpoint:
            if target_temp_low is not None and target_temp_high is not None:
                temp = (target_temp_low, target_temp_high)
        else:
            temp = kwargs.get(ATTR_TEMPERATURE)
        _LOGGER.debug("Set temperature: %s", temp)
        self.device.temperatureSetpoint = temp

    def set_operation_mode(self, operation_mode):
        """Set operation mode."""
        _LOGGER.debug('Set operation mode: %s', operation_mode)

        if operation_mode in [STATE_HEAT, STATE_COOL, STATE_OFF]:
            device_mode = operation_mode
        elif operation_mode == STATE_AUTO:
            device_mode = STATE_HEAT_COOL
        self.device.operationMode = device_mode.capitalize()

    @property
    def operation_list(self):
        """List of available operation modes."""
        return self._operation_list

    @property
    def current_hold_mode(self):
        """Return current hold mode."""
        return self._setpoint_status

    def set_hold_mode(self, hold_mode):
        """Set hold (PermanentHold, HoldUntil, NoHold, VacationHold) mode."""
        self.device.thermostatSetpointStatus = hold_mode

    def set_hold_period(self, period):
        """Set hold period (time)."""
        self.device.thermostatSetpointHoldUntil(period)

    @property
    def min_temp(self):
        """Identify min_temp in Lyric API or defaults if not available."""
        return self._min_temperature

    @property
    def max_temp(self):
        """Identify max_temp in Lyric API or defaults if not available."""
        return self._max_temperature

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        attrs = {"schedule": self._schedule_type}
        if self._schedule_sub_type:
            attrs["schedule_sub"] = self._schedule_sub_type
        if self._vacation_hold:
            attrs["vacation"] = self._vacation_hold
        if self._current_schedule_period_day:
            attrs["current_schedule_day"] = self._current_schedule_period_day
        if self._current_schedule_period:
            attrs["current_schedule_period"] = self._current_schedule_period
        if self._humidity:
            attrs["humidity"] = self._humidity
        if self._setpoint_status:
            attrs["setpoint_status"] = self._setpoint_status
        if self._dual_setpoint:
            attrs["dual_setpoint"] = self._dual_setpoint
        if self._vacation_hold:
            attrs["vacation_hold"] = self._vacation_hold
        if self._temperature_scale:
            attrs["temperature_scale"] = self._temperature_scale
        return attrs

    def update(self):
        """Get values from lyric."""
        if self.device:
            self._location = self.device.where
            self._name = self.device.name
            self._humidity = self.device.indoorHumidity
            self._temperature = self.device.indoorTemperature
            self._mode = self.device.operationMode.lower()
            self._setpoint_status = self.device.thermostatSetpointStatus
            self._target_temperature = self.device.temperatureSetpoint
            self._target_temp_heat = self.device.heatSetpoint
            self._target_temp_cool = self.device.coolSetpoint
            self._dual_setpoint = self.device.hasDualSetpointStatus
            self._min_temperature = self.device.minSetpoint
            self._max_temperature = self.device.maxSetpoint
            self._schedule_type = self.device.scheduleType
            self._schedule_sub_type = self.device.scheduleSubType
            self._vacation_hold = self.device.vacationHold
            if self.device.currentSchedulePeriod:
                csp = self.device.currentSchedulePeriod
                if 'period' in csp:
                    self._current_schedule_period = csp['period']
                if 'day' in csp:
                    self._current_schedule_period = csp['day']
            if self.device.units == 'Celsius':
                self._temperature_scale = TEMP_CELSIUS
            else:
                self._temperature_scale = TEMP_FAHRENHEIT
