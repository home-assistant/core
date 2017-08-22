"""
Support for Honeywell Lyric thermostats.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.lyric/
"""
import logging
from os import path
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
"""
replace custom_components.lyric with 
homeassistant.components.lyric when not 
placed in custom components
"""
from custom_components.lyric import DATA_LYRIC, CONF_FAN, CONF_AWAY_PERIODS
from homeassistant.components.climate import (
    ATTR_TARGET_TEMP_HIGH, ATTR_TARGET_TEMP_LOW, DOMAIN,
    ClimateDevice, PLATFORM_SCHEMA, STATE_AUTO,
    STATE_COOL, STATE_HEAT)
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_TEMPERATURE, CONF_SCAN_INTERVAL,
    STATE_ON, STATE_OFF, STATE_UNKNOWN, TEMP_CELSIUS,
    TEMP_FAHRENHEIT)
from homeassistant.config import load_yaml_config_file

DEPENDENCIES = ['lyric']
_LOGGER = logging.getLogger(__name__)

SERVICE_RESUME_PROGRAM = 'lyric_resume_program'
SERVICE_RESET_AWAY = 'lyric_reset_away'
STATE_HEAT_COOL = 'heat-cool'
HOLD_NO_HOLD = 'NoHold'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_SCAN_INTERVAL):
        vol.All(vol.Coerce(int), vol.Range(min=1))
})

RESUME_PROGRAM_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids
})

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Lyric thermostat."""

    if discovery_info is None:
        return

    _LOGGER.debug("climate discovery_info: %s" % discovery_info)   
    _LOGGER.debug("climate config: %s" % config)

    temp_unit = hass.config.units.temperature_unit
    has_fan = discovery_info.get(CONF_FAN)
    away_periods = discovery_info.get(CONF_AWAY_PERIODS, [])

    _LOGGER.debug('Set up Lyric climate platform')

    devices = [LyricThermostat(location, device, hass, temp_unit, has_fan, away_periods)
               for location, device in hass.data[DATA_LYRIC].thermostats()]

    add_devices(devices, True)

    def resume_program_service(service):
        """Resume the program on the target thermostats."""
        entity_id = service.data.get(ATTR_ENTITY_ID)

        _LOGGER.debug('resume_program_service entity_id: %s' % entity_id)

        if entity_id:
            target_thermostats = [device for device in devices
                                  if device.entity_id in entity_id]
        else:
            target_thermostats = devices

        for thermostat in target_thermostats:
            thermostat.set_hold_mode(HOLD_NO_HOLD)
            thermostat.away_override = False

    descriptions = load_yaml_config_file(
        path.join(path.dirname(__file__), 'services.yaml'))

    hass.services.register(
        DOMAIN, SERVICE_RESUME_PROGRAM, resume_program_service,
        descriptions.get(SERVICE_RESUME_PROGRAM),
        schema=RESUME_PROGRAM_SCHEMA)

class LyricThermostat(ClimateDevice):
    """Representation of a Lyric thermostat."""

    def __init__(self, location, device, hass, temp_unit, has_fan, away_periods):
        """Initialize the thermostat."""
        self._unit = temp_unit
        self.location = location
        self.device = device
        self._hass = hass

        self._away_periods = away_periods

        _LOGGER.debug("away periods: %s" % away_periods)
       
        # Not all lyric devices support cooling and heating remove unused
        self._operation_list = [STATE_OFF]

        # Add supported lyric thermostat features
        if self.device.can_heat:
            self._operation_list.append(STATE_HEAT)

        if self.device.can_cool:
            self._operation_list.append(STATE_COOL)

        if self.device.can_heat and self.device.can_cool:
            self._operation_list.append(STATE_AUTO)

        # feature of device
        self._has_fan = has_fan
        if (self._has_fan):
            self._fan_list = self.device.settings["fan"]["allowedModes"]
        # else:
        #    self._fan_list = None

        # data attributes
        self._away = None
        self._location = None
        self._name = None
        self._humidity = None
        self._target_temperature = None
        self._setpointStatus = None
        self._temperature = None
        self._temperature_scale = None
        self._target_temp_heat = None
        self._target_temp_cool = None
        self._dualSetpoint = None
        self._mode = None
        self._fan = None
        self._min_temperature = None
        self._max_temperature = None
        self._changeableValues = None
        self._scheduleType = None
        self._scheduleSubType = None
        self._scheduleCapabilities = None
        self._currentSchedulePeriod = None
        self._currentSchedulePeriodDay = None
        self._vacationHold = None
        self.away_override = False

    @property
    def name(self):
        """Return the name of the lyric, if any."""
        return self._name

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
        if not self._dualSetpoint:
            return self._target_temperature
        else:
            return None

    @property
    def target_temperature_low(self):
        """Return the upper bound temperature we try to reach."""
        if self._dualSetpoint:
            return self._target_temp_cool
        else:
            return None

    @property
    def target_temperature_high(self):
        """Return the upper bound temperature we try to reach."""
        if self._dualSetpoint:
            return self._target_temp_heat
        else:
            return None

    @property
    def is_away_mode_on(self):
        """Return if away mode is on."""
        if self.away_override:
            return self._away
        elif self._scheduleType == 'Timed' and self._away_periods:
            return self._currentSchedulePeriod in self._away_periods
        else:
            return self._away

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        target_temp_low = kwargs.get(ATTR_TARGET_TEMP_LOW)
        target_temp_high = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        if self._dualSetpoint:
            if target_temp_low is not None and target_temp_high is not None:
                temp = (target_temp_low, target_temp_high)
        else:
            temp = kwargs.get(ATTR_TEMPERATURE)
        _LOGGER.debug("Lyric set_temperature-output-value=%s", temp)
        self.device.temperatureSetpoint = temp

    def set_operation_mode(self, operation_mode):
        """Set operation mode."""
        _LOGGER.debug(operation_mode)
        _LOGGER.debug(operation_mode.capitalize())

        if operation_mode in [STATE_HEAT, STATE_COOL, STATE_OFF]:
            device_mode = operation_mode
        elif operation_mode == STATE_AUTO:
            device_mode = STATE_HEAT_COOL
        self.device.operationMode = device_mode.capitalize()

    @property
    def operation_list(self):
        """List of available operation modes."""
        return self._operation_list

    def turn_away_mode_on(self):
        """Turn away on."""
        self._away = True
        self.away_override = True
        self._hass.bus.fire('override_away_on', {
                                'entity_id': self.entity_id
                           })

    def turn_away_mode_off(self):
        """Turn away off."""
        self._away = False
        self.away_override = True
        self._hass.bus.fire('override_away_off', {
                                'entity_id': self.entity_id
                           })
    @property
    def current_hold_mode(self):
        """Return current hold mode."""
        return self._setpointStatus

    def set_hold_mode(self, hold_mode):
        """Set hold mode (PermanentHold, HoldUntil, NoHold,
        VacationHold, etc.)."""
        self.device.thermostatSetpointStatus = hold_mode

    @property
    def current_fan_mode(self):
        """Return whether the fan is on."""
        if self._has_fan:
            # Return whether the fan is on
            return self._fan
        else:
            # No Fan available so disable slider
            return None

    @property
    def fan_list(self):
        """List of available fan modes."""
        return self._fan_list

    def set_fan_mode(self, fan):
        """Set fan state."""
        self.device.fan = fan

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
        attrs = {"schedule": self._scheduleType, "away_override": self.away_override}
        if self._scheduleSubType:
            attrs["schedule_sub"] = self._scheduleSubType
        if self._vacationHold:
            attrs["vacation"] = self._vacationHold
        if self._currentSchedulePeriodDay:
            attrs["current_schedule_day"] = self._currentSchedulePeriodDay
        if self._currentSchedulePeriod:
            attrs["current_schedule_period"] = self._currentSchedulePeriod
        return attrs

    def update(self):
        """Cache value from python-lyric."""
        if self.device:
            self._location = self.device.where
            self._name = self.device.name
            self._humidity = self.device.indoorHumidity
            self._temperature = self.device.indoorTemperature
            self._mode = self.device.operationMode.lower()
            self._setpointStatus = self.device.thermostatSetpointStatus
            self._target_temperature = self.device.temperatureSetpoint
            self._target_temp_heat = self.device.heatSetpoint
            self._target_temp_cool = self.device.coolSetpoint
            self._dualSetpoint = self.device.hasDualSetpointStatus
            self._fan = self.device.fanMode
            if self.away_override == False:
                self._away = self.device.away
            self._min_temperature = self.device.minSetpoint
            self._max_temperature = self.device.maxSetpoint
            # self._changeableValues = self.device.changeableValues
            self._scheduleType = self.device.scheduleType
            self._scheduleSubType = self.device.scheduleSubType
            # self._scheduleCapabilities = self.device.scheduleCapabilities
            self._vacationHold = self.device.vacationHold
            if self.device.currentSchedulePeriod:
                if 'period' in  self.device.currentSchedulePeriod:
                    self._currentSchedulePeriod = self.device.currentSchedulePeriod['period']
                if 'day' in  self.device.currentSchedulePeriod:
                    self._currentSchedulePeriod = self.device.currentSchedulePeriod['day']
    
            if self.device.units == 'Celsius':
                self._temperature_scale = TEMP_CELSIUS
            else:
                self._temperature_scale = TEMP_FAHRENHEIT
