"""
Provides functionality to interact with thermostats.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/thermostat/
"""
import logging
import os
from numbers import Number

import voluptuous as vol

from homeassistant.helpers.entity_component import EntityComponent

from homeassistant.config import load_yaml_config_file
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA  # noqa
import homeassistant.helpers.config_validation as cv
from homeassistant.util.temperature import convert
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_TEMPERATURE, STATE_ON, STATE_OFF, STATE_UNKNOWN,
    TEMP_CELSIUS)

DOMAIN = "thermostat"

ENTITY_ID_FORMAT = DOMAIN + ".{}"
SCAN_INTERVAL = 60

SERVICE_SET_AWAY_MODE = "set_away_mode"
SERVICE_SET_TEMPERATURE = "set_temperature"
SERVICE_SET_FAN_MODE = "set_fan_mode"
SERVICE_SET_HVAC_MODE = "set_hvac_mode"

STATE_HEAT = "heat"
STATE_COOL = "cool"
STATE_IDLE = "idle"
STATE_AUTO = "auto"

ATTR_CURRENT_TEMPERATURE = "current_temperature"
ATTR_AWAY_MODE = "away_mode"
ATTR_FAN = "fan"
ATTR_HVAC_MODE = "hvac_mode"
ATTR_MAX_TEMP = "max_temp"
ATTR_MIN_TEMP = "min_temp"
ATTR_TEMPERATURE_LOW = "target_temp_low"
ATTR_TEMPERATURE_HIGH = "target_temp_high"
ATTR_OPERATION = "current_operation"

_LOGGER = logging.getLogger(__name__)

SET_AWAY_MODE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_AWAY_MODE): cv.boolean,
})
SET_TEMPERATURE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_TEMPERATURE): vol.Coerce(float),
})
SET_FAN_MODE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_FAN): cv.boolean,
})
SET_HVAC_MODE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_HVAC_MODE): cv.string,
})


def set_away_mode(hass, away_mode, entity_id=None):
    """Turn all or specified thermostat away mode on."""
    data = {
        ATTR_AWAY_MODE: away_mode
    }

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_SET_AWAY_MODE, data)


def set_temperature(hass, temperature, entity_id=None):
    """Set new target temperature."""
    data = {ATTR_TEMPERATURE: temperature}

    if entity_id is not None:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_SET_TEMPERATURE, data)


def set_fan_mode(hass, fan_mode, entity_id=None):
    """Turn all or specified thermostat fan mode on."""
    data = {
        ATTR_FAN: fan_mode
    }

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_SET_FAN_MODE, data)


def set_hvac_mode(hass, hvac_mode, entity_id=None):
    """Set specified thermostat hvac mode."""
    data = {
        ATTR_HVAC_MODE: hvac_mode
    }

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_SET_HVAC_MODE, data)


# pylint: disable=too-many-branches
def setup(hass, config):
    """Setup thermostats."""
    _LOGGER.warning('This component has been deprecated in favour of'
                    ' the "climate" component and will be removed '
                    'in the future. Please upgrade.')
    component = EntityComponent(_LOGGER, DOMAIN, hass, SCAN_INTERVAL)
    component.setup(config)

    descriptions = load_yaml_config_file(
        os.path.join(os.path.dirname(__file__), 'services.yaml'))

    def away_mode_set_service(service):
        """Set away mode on target thermostats."""
        target_thermostats = component.extract_from_service(service)

        away_mode = service.data[ATTR_AWAY_MODE]

        for thermostat in target_thermostats:
            if away_mode:
                thermostat.turn_away_mode_on()
            else:
                thermostat.turn_away_mode_off()

            thermostat.update_ha_state(True)

    hass.services.register(
        DOMAIN, SERVICE_SET_AWAY_MODE, away_mode_set_service,
        descriptions.get(SERVICE_SET_AWAY_MODE),
        schema=SET_AWAY_MODE_SCHEMA)

    def temperature_set_service(service):
        """Set temperature on the target thermostats."""
        target_thermostats = component.extract_from_service(service)

        temperature = service.data[ATTR_TEMPERATURE]

        for thermostat in target_thermostats:
            converted_temperature = convert(
                temperature, hass.config.units.temperature_unit,
                thermostat.unit_of_measurement)

            thermostat.set_temperature(converted_temperature)
            thermostat.update_ha_state(True)

    hass.services.register(
        DOMAIN, SERVICE_SET_TEMPERATURE, temperature_set_service,
        descriptions.get(SERVICE_SET_TEMPERATURE),
        schema=SET_TEMPERATURE_SCHEMA)

    def fan_mode_set_service(service):
        """Set fan mode on target thermostats."""
        target_thermostats = component.extract_from_service(service)

        fan_mode = service.data[ATTR_FAN]

        for thermostat in target_thermostats:
            if fan_mode:
                thermostat.turn_fan_on()
            else:
                thermostat.turn_fan_off()

            thermostat.update_ha_state(True)

    hass.services.register(
        DOMAIN, SERVICE_SET_FAN_MODE, fan_mode_set_service,
        descriptions.get(SERVICE_SET_FAN_MODE),
        schema=SET_FAN_MODE_SCHEMA)

    def hvac_mode_set_service(service):
        """Set hvac mode on target thermostats."""
        target_thermostats = component.extract_from_service(service)

        hvac_mode = service.data[ATTR_HVAC_MODE]

        for thermostat in target_thermostats:
            thermostat.set_hvac_mode(hvac_mode)

            thermostat.update_ha_state(True)

    hass.services.register(
        DOMAIN, SERVICE_SET_HVAC_MODE, hvac_mode_set_service,
        descriptions.get(SERVICE_SET_HVAC_MODE),
        schema=SET_HVAC_MODE_SCHEMA)

    return True


class ThermostatDevice(Entity):
    """Representation of a thermostat."""

    # pylint: disable=no-self-use
    @property
    def state(self):
        """Return the current state."""
        return self.target_temperature or STATE_UNKNOWN

    @property
    def state_attributes(self):
        """Return the optional state attributes."""
        data = {
            ATTR_CURRENT_TEMPERATURE:
            self._convert_for_display(self.current_temperature),
            ATTR_MIN_TEMP: self._convert_for_display(self.min_temp),
            ATTR_MAX_TEMP: self._convert_for_display(self.max_temp),
            ATTR_TEMPERATURE:
            self._convert_for_display(self.target_temperature),
            ATTR_TEMPERATURE_LOW:
            self._convert_for_display(self.target_temperature_low),
            ATTR_TEMPERATURE_HIGH:
            self._convert_for_display(self.target_temperature_high),
        }

        operation = self.operation
        if operation is not None:
            data[ATTR_OPERATION] = operation

        is_away = self.is_away_mode_on
        if is_away is not None:
            data[ATTR_AWAY_MODE] = STATE_ON if is_away else STATE_OFF

        is_fan_on = self.is_fan_on
        if is_fan_on is not None:
            data[ATTR_FAN] = STATE_ON if is_fan_on else STATE_OFF

        return data

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        raise NotImplementedError

    @property
    def current_temperature(self):
        """Return the current temperature."""
        raise NotImplementedError

    @property
    def operation(self):
        """Return current operation ie. heat, cool, idle."""
        return None

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        raise NotImplementedError

    @property
    def target_temperature_low(self):
        """Return the lower bound temperature we try to reach."""
        return self.target_temperature

    @property
    def target_temperature_high(self):
        """Return the upper bound temperature we try to reach."""
        return self.target_temperature

    @property
    def is_away_mode_on(self):
        """Return true if away mode is on."""
        return None

    @property
    def is_fan_on(self):
        """Return true if the fan is on."""
        return None

    def set_temperature(self, temperature):
        """Set new target temperature."""
        raise NotImplementedError()

    def set_hvac_mode(self, hvac_mode):
        """Set hvac mode."""
        raise NotImplementedError()

    def turn_away_mode_on(self):
        """Turn away mode on."""
        raise NotImplementedError()

    def turn_away_mode_off(self):
        """Turn away mode off."""
        raise NotImplementedError()

    def turn_fan_on(self):
        """Turn fan on."""
        raise NotImplementedError()

    def turn_fan_off(self):
        """Turn fan off."""
        raise NotImplementedError()

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return convert(7, TEMP_CELSIUS, self.unit_of_measurement)

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return convert(35, TEMP_CELSIUS, self.unit_of_measurement)

    def _convert_for_display(self, temp):
        """Convert temperature into preferred units for display purposes."""
        if temp is None or not isinstance(temp, Number):
            return temp

        value = self.hass.config.units.temperature(temp,
                                                   self.unit_of_measurement)

        if self.hass.config.units.is_metric:
            decimal_count = 1
        else:
            # Users of fahrenheit generally expect integer units.
            decimal_count = 0

        return round(value, decimal_count)
