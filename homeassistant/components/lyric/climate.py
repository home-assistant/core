"""
Support for Honeywell Lyric thermostats.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/lyric
"""
import logging
from typing import List, Optional

import voluptuous as vol

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    ATTR_TARGET_TEMP_HIGH, ATTR_TARGET_TEMP_LOW,
    HVAC_MODE_OFF, HVAC_MODE_HEAT, HVAC_MODE_COOL, HVAC_MODE_HEAT_COOL,
    SUPPORT_TARGET_TEMPERATURE, SUPPORT_PRESET_MODE)
from homeassistant.const import (ATTR_ENTITY_ID, ATTR_TEMPERATURE, ATTR_TIME,
                                 TEMP_CELSIUS, TEMP_FAHRENHEIT)
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
import homeassistant.helpers.config_validation as cv
from . import LyricDeviceEntity
from .const import DATA_LYRIC_CLIENT, DATA_LYRIC_DEVICES, DOMAIN

_LOGGER = logging.getLogger(__name__)

SERVICE_HOLD_TIME = 'set_hold_time'
PRESET_NO_HOLD = 'NoHold'
PRESET_TEMPORARY_HOLD = 'TemporaryHold'
PRESET_PERMANENT_HOLD = 'PermanentHold'
PRESET_VACATION_HOLD = 'VacationHold'

SUPPORT_FLAGS = (SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE)

HOLD_PERIOD_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.comp_entity_ids,
    vol.Required(ATTR_TIME): cv.string
})

LYRIC_HVAC_MODES = {
    HVAC_MODE_OFF: 'OFF',
    HVAC_MODE_HEAT: 'HEAT',
    HVAC_MODE_COOL: 'COOL',
    HVAC_MODE_HEAT_COOL: 'HEAT_COOL'
}

HVAC_MODES = {
    'OFF': HVAC_MODE_OFF,
    'HEAT': HVAC_MODE_HEAT,
    'COOL': HVAC_MODE_COOL,
    'HEAT_COOL': HVAC_MODE_HEAT_COOL
}


async def async_setup_entry(
        hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up Lyric thermostat based on a config entry."""
    lyric = hass.data[DOMAIN][DATA_LYRIC_CLIENT]

    try:
        devices = lyric.devices()
    except Exception as exception:
        raise PlatformNotReady from exception

    hass.data[DOMAIN][DATA_LYRIC_DEVICES] = devices

    temp_unit = hass.config.units.temperature_unit
    entities = [LyricThermostat(device, location, temp_unit)
                for location, device in lyric.devices()]

    async_add_entities(entities, True)

    async def hold_time_service(service) -> None:
        """Set the time to hold until."""
        entity_ids = service.data[ATTR_ENTITY_ID]
        time = service.data[ATTR_TIME]

        _LOGGER.debug('hold_time_service: %s; %s', entity_ids, time)

        if entity_ids == 'all':
            target_thermostats = devices
        elif entity_ids:
            target_thermostats = [device for device in devices
                                  if device.entity_id in entity_ids]
        else:
            target_thermostats = devices

        for thermostat in target_thermostats:
            await thermostat.async_set_preset_period(time)

    hass.services.async_register(
        DOMAIN, SERVICE_HOLD_TIME, hold_time_service,
        schema=HOLD_PERIOD_SCHEMA)


async def async_unload_entry(
        hass: HomeAssistantType, entry: ConfigType
) -> bool:
    """Unload Lyric thermostat config entry."""
    hass.services.async_remove(DOMAIN, SERVICE_HOLD_TIME)


class LyricThermostat(LyricDeviceEntity, ClimateDevice):
    """Representation of a Lyric thermostat."""

    def __init__(self, device, location, temp_unit) -> None:
        """Initialize the thermostat."""
        unique_id = '{}_climate'.format(device.macID)
        self._unit = temp_unit

        # Setup supported hvac modes
        self._hvac_modes = [HVAC_MODE_OFF]

        # Add supported lyric thermostat features
        if device.can_heat:
            self._hvac_modes.append(HVAC_MODE_HEAT)

        if device.can_cool:
            self._hvac_modes.append(HVAC_MODE_COOL)

        if device.can_heat and device.can_cool:
            self._hvac_modes.append(HVAC_MODE_HEAT_COOL)

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
        self._next_period_time = None
        self._schedule_type = None
        self._schedule_sub_type = None
        self._current_schedule_period = None
        self._current_schedule_period_day = None
        self._vacation_hold = None

        super().__init__(device, location, unique_id, None, None, None)

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return self._temperature_scale

    @property
    def current_temperature(self) -> Optional[float]:
        """Return the current temperature."""
        return self._temperature

    @property
    def current_humidity(self) -> Optional[int]:
        """Return the current humidity."""
        return self._humidity

    @property
    def hvac_mode(self) -> str:
        """Return the hvac mode."""
        return HVAC_MODES[self._mode]

    @property
    def hvac_modes(self) -> List[str]:
        """List of available hvac modes."""
        return self._hvac_modes

    @property
    def target_temperature(self) -> Optional[float]:
        """Return the temperature we try to reach."""
        target_temperature = None
        if not self._dual_setpoint:
            target_temperature = self._target_temperature
        return target_temperature

    @property
    def target_temperature_low(self) -> Optional[float]:
        """Return the upper bound temperature we try to reach."""
        target_temperature_low = None
        if self._dual_setpoint:
            target_temperature_low = self._target_temp_cool
        return target_temperature_low

    @property
    def target_temperature_high(self) -> Optional[float]:
        """Return the upper bound temperature we try to reach."""
        target_temperature_high = None
        if self._dual_setpoint:
            target_temperature_high = self._target_temp_heat
        return target_temperature_high

    @property
    def preset_mode(self) -> Optional[str]:
        """Return current preset mode."""
        return self._setpoint_status

    @property
    def preset_modes(self) -> Optional[List[str]]:
        """Return preset modes."""
        return [PRESET_NO_HOLD, PRESET_TEMPORARY_HOLD,
                PRESET_PERMANENT_HOLD, PRESET_VACATION_HOLD]

    @property
    def min_temp(self) -> float:
        """Identify min_temp in Lyric API or defaults if not available."""
        return self._min_temperature

    @property
    def max_temp(self) -> float:
        """Identify max_temp in Lyric API or defaults if not available."""
        return self._max_temperature

    @property
    def device_state_attributes(self) -> Optional[List[str]]:
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
        if self._next_period_time:
            attrs["next_period_time"] = self._next_period_time
        if self._setpoint_status:
            attrs["setpoint_status"] = self._setpoint_status
        if self._dual_setpoint:
            attrs["dual_setpoint"] = self._dual_setpoint
        if self._vacation_hold:
            attrs["vacation_hold"] = self._vacation_hold
        if self._temperature_scale:
            attrs["temperature_scale"] = self._temperature_scale
        return attrs

    async def async_set_temperature(self, **kwargs) -> None:
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

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set hvac mode."""
        _LOGGER.debug('Set hvac mode: %s', hvac_mode)
        self.device.operationMode = LYRIC_HVAC_MODES[hvac_mode]

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset (PermanentHold, HoldUntil, NoHold, VacationHold) mode."""
        self.device.thermostatSetpointStatus = preset_mode

    async def async_set_preset_period(self, period: str) -> None:
        """Set preset period (time)."""
        self.device.thermostatSetpointHoldUntil(period)

    async def _lyric_update(self) -> None:
        """Get values from lyric."""
        if self.device:
            self._location = self.device.where
            self._name = self.device.name
            self._humidity = self.device.indoorHumidity
            self._temperature = self.device.indoorTemperature
            self._mode = self.device.operationMode.upper()
            self._next_period_time = self.device.nextPeriodTime
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
