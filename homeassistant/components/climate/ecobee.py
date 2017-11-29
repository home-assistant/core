"""
Platform for Ecobee Thermostats.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.ecobee/
"""
import logging
from os import path

import voluptuous as vol

from homeassistant.components import ecobee
from homeassistant.components.climate import (
    DOMAIN, STATE_COOL, STATE_HEAT, STATE_AUTO, STATE_IDLE, ClimateDevice,
    ATTR_TARGET_TEMP_LOW, ATTR_TARGET_TEMP_HIGH, SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_AWAY_MODE, SUPPORT_HOLD_MODE, SUPPORT_OPERATION_MODE,
    SUPPORT_TARGET_HUMIDITY_LOW, SUPPORT_TARGET_HUMIDITY_HIGH)
from homeassistant.const import (
    ATTR_ENTITY_ID, STATE_OFF, STATE_ON, ATTR_TEMPERATURE, TEMP_FAHRENHEIT)
from homeassistant.config import load_yaml_config_file
import homeassistant.helpers.config_validation as cv

_CONFIGURING = {}
_LOGGER = logging.getLogger(__name__)

ATTR_FAN_MIN_ON_TIME = 'fan_min_on_time'
ATTR_RESUME_ALL = 'resume_all'

DEFAULT_RESUME_ALL = False
TEMPERATURE_HOLD = 'temp'
VACATION_HOLD = 'vacation'
AWAY_MODE = 'awayMode'

DEPENDENCIES = ['ecobee']

SERVICE_SET_FAN_MIN_ON_TIME = 'ecobee_set_fan_min_on_time'
SERVICE_RESUME_PROGRAM = 'ecobee_resume_program'

SET_FAN_MIN_ON_TIME_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_FAN_MIN_ON_TIME): vol.Coerce(int),
})

RESUME_PROGRAM_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Optional(ATTR_RESUME_ALL, default=DEFAULT_RESUME_ALL): cv.boolean,
})

SUPPORT_FLAGS = (SUPPORT_TARGET_TEMPERATURE | SUPPORT_AWAY_MODE |
                 SUPPORT_HOLD_MODE | SUPPORT_OPERATION_MODE |
                 SUPPORT_TARGET_HUMIDITY_LOW | SUPPORT_TARGET_HUMIDITY_HIGH)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Ecobee Thermostat Platform."""
    if discovery_info is None:
        return
    data = ecobee.NETWORK
    hold_temp = discovery_info['hold_temp']
    _LOGGER.info(
        "Loading ecobee thermostat component with hold_temp set to %s",
        hold_temp)
    devices = [Thermostat(data, index, hold_temp)
               for index in range(len(data.ecobee.thermostats))]
    add_devices(devices)

    def fan_min_on_time_set_service(service):
        """Set the minimum fan on time on the target thermostats."""
        entity_id = service.data.get(ATTR_ENTITY_ID)
        fan_min_on_time = service.data[ATTR_FAN_MIN_ON_TIME]

        if entity_id:
            target_thermostats = [device for device in devices
                                  if device.entity_id in entity_id]
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
            target_thermostats = [device for device in devices
                                  if device.entity_id in entity_id]
        else:
            target_thermostats = devices

        for thermostat in target_thermostats:
            thermostat.resume_program(resume_all)

            thermostat.schedule_update_ha_state(True)

    descriptions = load_yaml_config_file(
        path.join(path.dirname(__file__), 'services.yaml'))

    hass.services.register(
        DOMAIN, SERVICE_SET_FAN_MIN_ON_TIME, fan_min_on_time_set_service,
        descriptions.get(SERVICE_SET_FAN_MIN_ON_TIME),
        schema=SET_FAN_MIN_ON_TIME_SCHEMA)

    hass.services.register(
        DOMAIN, SERVICE_RESUME_PROGRAM, resume_program_set_service,
        descriptions.get(SERVICE_RESUME_PROGRAM),
        schema=RESUME_PROGRAM_SCHEMA)


class Thermostat(ClimateDevice):
    """A thermostat class for Ecobee."""

    def __init__(self, data, thermostat_index, hold_temp):
        """Initialize the thermostat."""
        self.data = data
        self.thermostat_index = thermostat_index
        self.thermostat = self.data.ecobee.get_thermostat(
            self.thermostat_index)
        self._name = self.thermostat['name']
        self.hold_temp = hold_temp
        self.vacation = None
        self._climate_list = self.climate_list
        self._operation_list = ['auto', 'auxHeatOnly', 'cool',
                                'heat', 'off']
        self.update_without_throttle = False

    def update(self):
        """Get the latest state from the thermostat."""
        if self.update_without_throttle:
            self.data.update(no_throttle=True)
            self.update_without_throttle = False
        else:
            self.data.update()

        self.thermostat = self.data.ecobee.get_thermostat(
            self.thermostat_index)

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def name(self):
        """Return the name of the Ecobee Thermostat."""
        return self.thermostat['name']

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_FAHRENHEIT

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self.thermostat['runtime']['actualTemperature'] / 10.0

    @property
    def target_temperature_low(self):
        """Return the lower bound temperature we try to reach."""
        if self.current_operation == STATE_AUTO:
            return self.thermostat['runtime']['desiredHeat'] / 10.0
        return None

    @property
    def target_temperature_high(self):
        """Return the upper bound temperature we try to reach."""
        if self.current_operation == STATE_AUTO:
            return self.thermostat['runtime']['desiredCool'] / 10.0
        return None

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        if self.current_operation == STATE_AUTO:
            return None
        if self.current_operation == STATE_HEAT:
            return self.thermostat['runtime']['desiredHeat'] / 10.0
        elif self.current_operation == STATE_COOL:
            return self.thermostat['runtime']['desiredCool'] / 10.0
        return None

    @property
    def desired_fan_mode(self):
        """Return the desired fan mode of operation."""
        return self.thermostat['runtime']['desiredFanMode']

    @property
    def fan(self):
        """Return the current fan state."""
        if 'fan' in self.thermostat['equipmentStatus']:
            return STATE_ON
        return STATE_OFF

    @property
    def current_hold_mode(self):
        """Return current hold mode."""
        mode = self._current_hold_mode
        return None if mode == AWAY_MODE else mode

    @property
    def _current_hold_mode(self):
        events = self.thermostat['events']
        for event in events:
            if event['running']:
                if event['type'] == 'hold':
                    if event['holdClimateRef'] == 'away':
                        if int(event['endDate'][0:4]) - \
                           int(event['startDate'][0:4]) <= 1:
                            # A temporary hold from away climate is a hold
                            return 'away'
                        # A permanent hold from away climate
                        return AWAY_MODE
                    elif event['holdClimateRef'] != "":
                        # Any other hold based on climate
                        return event['holdClimateRef']
                    # Any hold not based on a climate is a temp hold
                    return TEMPERATURE_HOLD
                elif event['type'].startswith('auto'):
                    # All auto modes are treated as holds
                    return event['type'][4:].lower()
                elif event['type'] == 'vacation':
                    self.vacation = event['name']
                    return VACATION_HOLD
        return None

    @property
    def current_operation(self):
        """Return current operation."""
        if self.operation_mode == 'auxHeatOnly' or \
           self.operation_mode == 'heatPump':
            return STATE_HEAT
        return self.operation_mode

    @property
    def operation_list(self):
        """Return the operation modes list."""
        return self._operation_list

    @property
    def operation_mode(self):
        """Return current operation ie. heat, cool, idle."""
        return self.thermostat['settings']['hvacMode']

    @property
    def mode(self):
        """Return current mode, as the user-visible name."""
        cur = self.thermostat['program']['currentClimateRef']
        climates = self.thermostat['program']['climates']
        current = list(filter(lambda x: x['climateRef'] == cur, climates))
        return current[0]['name']

    @property
    def fan_min_on_time(self):
        """Return current fan minimum on time."""
        return self.thermostat['settings']['fanMinOnTime']

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        # Move these to Thermostat Device and make them global
        status = self.thermostat['equipmentStatus']
        operation = None
        if status == '':
            operation = STATE_IDLE
        elif 'Cool' in status:
            operation = STATE_COOL
        elif 'auxHeat' in status:
            operation = STATE_HEAT
        elif 'heatPump' in status:
            operation = STATE_HEAT
        else:
            operation = status
        return {
            "actual_humidity": self.thermostat['runtime']['actualHumidity'],
            "fan": self.fan,
            "mode": self.mode,
            "operation": operation,
            "climate_list": self.climate_list,
            "fan_min_on_time": self.fan_min_on_time
        }

    @property
    def is_away_mode_on(self):
        """Return true if away mode is on."""
        return self._current_hold_mode == AWAY_MODE

    @property
    def is_aux_heat_on(self):
        """Return true if aux heater."""
        return 'auxHeat' in self.thermostat['equipmentStatus']

    def turn_away_mode_on(self):
        """Turn away mode on by setting it on away hold indefinitely."""
        if self._current_hold_mode != AWAY_MODE:
            self.data.ecobee.set_climate_hold(self.thermostat_index, 'away',
                                              'indefinite')
            self.update_without_throttle = True

    def turn_away_mode_off(self):
        """Turn away off."""
        if self._current_hold_mode == AWAY_MODE:
            self.data.ecobee.resume_program(self.thermostat_index)
            self.update_without_throttle = True

    def set_hold_mode(self, hold_mode):
        """Set hold mode (away, home, temp, sleep, etc.)."""
        hold = self.current_hold_mode

        if hold == hold_mode:
            # no change, so no action required
            return
        elif hold_mode == 'None' or hold_mode is None:
            if hold == VACATION_HOLD:
                self.data.ecobee.delete_vacation(
                    self.thermostat_index, self.vacation)
            else:
                self.data.ecobee.resume_program(self.thermostat_index)
        else:
            if hold_mode == TEMPERATURE_HOLD:
                self.set_temp_hold(self.current_temperature)
            else:
                self.data.ecobee.set_climate_hold(
                    self.thermostat_index, hold_mode, self.hold_preference())
        self.update_without_throttle = True

    def set_auto_temp_hold(self, heat_temp, cool_temp):
        """Set temperature hold in auto mode."""
        if cool_temp is not None:
            cool_temp_setpoint = cool_temp
        else:
            cool_temp_setpoint = (
                self.thermostat['runtime']['desiredCool'] / 10.0)

        if heat_temp is not None:
            heat_temp_setpoint = heat_temp
        else:
            heat_temp_setpoint = (
                self.thermostat['runtime']['desiredCool'] / 10.0)

        self.data.ecobee.set_hold_temp(self.thermostat_index,
                                       cool_temp_setpoint, heat_temp_setpoint,
                                       self.hold_preference())
        _LOGGER.debug("Setting ecobee hold_temp to: heat=%s, is=%s, "
                      "cool=%s, is=%s", heat_temp, isinstance(
                          heat_temp, (int, float)), cool_temp,
                      isinstance(cool_temp, (int, float)))

        self.update_without_throttle = True

    def set_temp_hold(self, temp):
        """Set temperature hold in modes other than auto."""
        # Set arbitrary range when not in auto mode
        if self.current_operation == STATE_HEAT:
            heat_temp = temp
            cool_temp = temp + 20
        elif self.current_operation == STATE_COOL:
            heat_temp = temp - 20
            cool_temp = temp
        else:
            # In auto mode set temperature between
            heat_temp = temp - 10
            cool_temp = temp + 10
        self.set_auto_temp_hold(heat_temp, cool_temp)

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        low_temp = kwargs.get(ATTR_TARGET_TEMP_LOW)
        high_temp = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        temp = kwargs.get(ATTR_TEMPERATURE)

        if self.current_operation == STATE_AUTO and (low_temp is not None or
                                                     high_temp is not None):
            self.set_auto_temp_hold(low_temp, high_temp)
        elif temp is not None:
            self.set_temp_hold(temp)
        else:
            _LOGGER.error(
                "Missing valid arguments for set_temperature in %s", kwargs)

    def set_humidity(self, humidity):
        """Set the humidity level."""
        self.data.ecobee.set_humidity(self.thermostat_index, humidity)

    def set_operation_mode(self, operation_mode):
        """Set HVAC mode (auto, auxHeatOnly, cool, heat, off)."""
        self.data.ecobee.set_hvac_mode(self.thermostat_index, operation_mode)
        self.update_without_throttle = True

    def set_fan_min_on_time(self, fan_min_on_time):
        """Set the minimum fan on time."""
        self.data.ecobee.set_fan_min_on_time(
            self.thermostat_index, fan_min_on_time)
        self.update_without_throttle = True

    def resume_program(self, resume_all):
        """Resume the thermostat schedule program."""
        self.data.ecobee.resume_program(
            self.thermostat_index, 'true' if resume_all else 'false')
        self.update_without_throttle = True

    def hold_preference(self):
        """Return user preference setting for hold time."""
        # Values returned from thermostat are 'useEndTime4hour',
        # 'useEndTime2hour', 'nextTransition', 'indefinite', 'askMe'
        default = self.thermostat['settings']['holdAction']
        if default == 'nextTransition':
            return default
        # add further conditions if other hold durations should be
        # supported; note that this should not include 'indefinite'
        # as an indefinite away hold is interpreted as away_mode
        return 'nextTransition'

    @property
    def climate_list(self):
        """Return the list of climates currently available."""
        climates = self.thermostat['program']['climates']
        return list(map((lambda x: x['name']), climates))
