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
    DOMAIN, STATE_COOL, STATE_HEAT, STATE_IDLE, ClimateDevice,
    ATTR_TARGET_TEMP_LOW, ATTR_TARGET_TEMP_HIGH)
from homeassistant.const import (
    ATTR_ENTITY_ID, STATE_OFF, STATE_ON, TEMP_FAHRENHEIT, TEMP_CELSIUS)
from homeassistant.config import load_yaml_config_file
import homeassistant.helpers.config_validation as cv

_CONFIGURING = {}
_LOGGER = logging.getLogger(__name__)

ATTR_FAN_MIN_ON_TIME = 'fan_min_on_time'

DEPENDENCIES = ['ecobee']

SERVICE_SET_FAN_MIN_ON_TIME = 'ecobee_set_fan_min_on_time'

SET_FAN_MIN_ON_TIME_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_FAN_MIN_ON_TIME): vol.Coerce(int),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Ecobee Thermostat Platform."""
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
        entity_id = service.data.get('entity_id')

        if entity_id:
            target_thermostats = [device for device in devices
                                  if device.entity_id == entity_id]
        else:
            target_thermostats = devices

        fan_min_on_time = service.data[ATTR_FAN_MIN_ON_TIME]

        for thermostat in target_thermostats:
            thermostat.set_fan_min_on_time(str(fan_min_on_time))

            thermostat.update_ha_state(True)

    descriptions = load_yaml_config_file(
        path.join(path.dirname(__file__), 'services.yaml'))

    hass.services.register(
        DOMAIN, SERVICE_SET_FAN_MIN_ON_TIME, fan_min_on_time_set_service,
        descriptions.get(SERVICE_SET_FAN_MIN_ON_TIME),
        schema=SET_FAN_MIN_ON_TIME_SCHEMA)


# pylint: disable=too-many-public-methods, abstract-method
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
    def name(self):
        """Return the name of the Ecobee Thermostat."""
        return self.thermostat['name']

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        if self.thermostat['settings']['useCelsius']:
            return TEMP_CELSIUS
        else:
            return TEMP_FAHRENHEIT

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self.thermostat['runtime']['actualTemperature'] / 10

    @property
    def target_temperature_low(self):
        """Return the lower bound temperature we try to reach."""
        return int(self.thermostat['runtime']['desiredHeat'] / 10)

    @property
    def target_temperature_high(self):
        """Return the upper bound temperature we try to reach."""
        return int(self.thermostat['runtime']['desiredCool'] / 10)

    @property
    def desired_fan_mode(self):
        """Return the desired fan mode of operation."""
        return self.thermostat['runtime']['desiredFanMode']

    @property
    def fan(self):
        """Return the current fan state."""
        if 'fan' in self.thermostat['equipmentStatus']:
            return STATE_ON
        else:
            return STATE_OFF

    @property
    def current_operation(self):
        """Return current operation."""
        if self.operation_mode == 'auxHeatOnly' or \
           self.operation_mode == 'heatPump':
            return STATE_HEAT
        else:
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
        """Return current mode ie. home, away, sleep."""
        return self.thermostat['program']['currentClimateRef']

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
            "fan_min_on_time": self.fan_min_on_time
        }

    @property
    def is_away_mode_on(self):
        """Return true if away mode is on."""
        mode = self.mode
        events = self.thermostat['events']
        for event in events:
            if event['running']:
                mode = event['holdClimateRef']
                break
        return 'away' in mode

    def turn_away_mode_on(self):
        """Turn away on."""
        if self.hold_temp:
            self.data.ecobee.set_climate_hold(self.thermostat_index,
                                              "away", "indefinite")
        else:
            self.data.ecobee.set_climate_hold(self.thermostat_index, "away")
        self.update_without_throttle = True

    def turn_away_mode_off(self):
        """Turn away off."""
        self.data.ecobee.resume_program(self.thermostat_index)
        self.update_without_throttle = True

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        if kwargs.get(ATTR_TARGET_TEMP_LOW) is not None and \
           kwargs.get(ATTR_TARGET_TEMP_HIGH) is not None:
            high_temp = int(kwargs.get(ATTR_TARGET_TEMP_LOW))
            low_temp = int(kwargs.get(ATTR_TARGET_TEMP_HIGH))

        if self.hold_temp:
            self.data.ecobee.set_hold_temp(self.thermostat_index, low_temp,
                                           high_temp, "indefinite")
            _LOGGER.debug("Setting ecobee hold_temp to: low=%s, is=%s, "
                          "high=%s, is=%s", low_temp, isinstance(
                              low_temp, (int, float)), high_temp,
                          isinstance(high_temp, (int, float)))
        else:
            self.data.ecobee.set_hold_temp(self.thermostat_index, low_temp,
                                           high_temp)
            _LOGGER.debug("Setting ecobee temp to: low=%s, is=%s, "
                          "high=%s, is=%s", low_temp, isinstance(
                              low_temp, (int, float)), high_temp,
                          isinstance(high_temp, (int, float)))
        self.update_without_throttle = True

    def set_operation_mode(self, operation_mode):
        """Set HVAC mode (auto, auxHeatOnly, cool, heat, off)."""
        self.data.ecobee.set_hvac_mode(self.thermostat_index, operation_mode)
        self.update_without_throttle = True

    def set_fan_min_on_time(self, fan_min_on_time):
        """Set the minimum fan on time."""
        self.data.ecobee.set_fan_min_on_time(self.thermostat_index,
                                             fan_min_on_time)
        self.update_without_throttle = True

    # Home and Sleep mode aren't used in UI yet:

    # def turn_home_mode_on(self):
    #     """ Turns home mode on. """
    #     self.data.ecobee.set_climate_hold(self.thermostat_index, "home")

    # def turn_home_mode_off(self):
    #     """ Turns home mode off. """
    #     self.data.ecobee.resume_program(self.thermostat_index)

    # def turn_sleep_mode_on(self):
    #     """ Turns sleep mode on. """
    #     self.data.ecobee.set_climate_hold(self.thermostat_index, "sleep")

    # def turn_sleep_mode_off(self):
    #     """ Turns sleep mode off. """
    #     self.data.ecobee.resume_program(self.thermostat_index)
