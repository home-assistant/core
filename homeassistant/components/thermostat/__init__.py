"""
Provides functionality to interact with thermostats.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/thermostat/
"""
import logging
import os

from homeassistant.helpers.entity_component import EntityComponent

from homeassistant.config import load_yaml_config_file
import homeassistant.util as util
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.temperature import convert
from homeassistant.components import ecobee
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_TEMPERATURE, STATE_ON, STATE_OFF, STATE_UNKNOWN,
    TEMP_CELCIUS)

DOMAIN = "thermostat"

ENTITY_ID_FORMAT = DOMAIN + ".{}"
SCAN_INTERVAL = 60

SERVICE_SET_AWAY_MODE = "set_away_mode"
SERVICE_SET_TEMPERATURE = "set_temperature"
SERVICE_SET_FAN_MODE = "set_fan_mode"

STATE_HEAT = "heat"
STATE_COOL = "cool"
STATE_IDLE = "idle"

ATTR_CURRENT_TEMPERATURE = "current_temperature"
ATTR_AWAY_MODE = "away_mode"
ATTR_FAN = "fan"
ATTR_MAX_TEMP = "max_temp"
ATTR_MIN_TEMP = "min_temp"
ATTR_TEMPERATURE_LOW = "target_temp_low"
ATTR_TEMPERATURE_HIGH = "target_temp_high"
ATTR_OPERATION = "current_operation"

_LOGGER = logging.getLogger(__name__)

DISCOVERY_PLATFORMS = {
    ecobee.DISCOVER_THERMOSTAT: 'ecobee',
}


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


# pylint: disable=too-many-branches
def setup(hass, config):
    """Setup thermostats."""
    component = EntityComponent(_LOGGER, DOMAIN, hass,
                                SCAN_INTERVAL, DISCOVERY_PLATFORMS)
    component.setup(config)

    descriptions = load_yaml_config_file(
        os.path.join(os.path.dirname(__file__), 'services.yaml'))

    def away_mode_set_service(service):
        """Set away mode on target thermostats."""
        target_thermostats = component.extract_from_service(service)

        away_mode = service.data.get(ATTR_AWAY_MODE)

        if away_mode is None:
            _LOGGER.error(
                "Received call to %s without attribute %s",
                SERVICE_SET_AWAY_MODE, ATTR_AWAY_MODE)
            return

        for thermostat in target_thermostats:
            if away_mode:
                thermostat.turn_away_mode_on()
            else:
                thermostat.turn_away_mode_off()

            thermostat.update_ha_state(True)

    hass.services.register(
        DOMAIN, SERVICE_SET_AWAY_MODE, away_mode_set_service,
        descriptions.get(SERVICE_SET_AWAY_MODE))

    def temperature_set_service(service):
        """Set temperature on the target thermostats."""
        target_thermostats = component.extract_from_service(service)

        temperature = util.convert(
            service.data.get(ATTR_TEMPERATURE), float)

        if temperature is None:
            return

        for thermostat in target_thermostats:
            thermostat.set_temperature(convert(
                temperature, hass.config.temperature_unit,
                thermostat.unit_of_measurement))

            thermostat.update_ha_state(True)

    hass.services.register(
        DOMAIN, SERVICE_SET_TEMPERATURE, temperature_set_service,
        descriptions.get(SERVICE_SET_TEMPERATURE))

    def fan_mode_set_service(service):
        """Set fan mode on target thermostats."""
        target_thermostats = component.extract_from_service(service)

        fan_mode = service.data.get(ATTR_FAN)

        if fan_mode is None:
            _LOGGER.error(
                "Received call to %s without attribute %s",
                SERVICE_SET_FAN_MODE, ATTR_FAN)
            return

        for thermostat in target_thermostats:
            if fan_mode:
                thermostat.turn_fan_on()
            else:
                thermostat.turn_fan_off()

            thermostat.update_ha_state(True)

    hass.services.register(
        DOMAIN, SERVICE_SET_FAN_MODE, fan_mode_set_service,
        descriptions.get(SERVICE_SET_FAN_MODE))

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
            self._convert(self.current_temperature, 1),
            ATTR_MIN_TEMP: self._convert(self.min_temp, 1),
            ATTR_MAX_TEMP: self._convert(self.max_temp, 1),
            ATTR_TEMPERATURE: self._convert(self.target_temperature, 1),
            ATTR_TEMPERATURE_LOW:
            self._convert(self.target_temperature_low, 1),
            ATTR_TEMPERATURE_HIGH:
            self._convert(self.target_temperature_high, 1),
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

    def set_temperate(self, temperature):
        """Set new target temperature."""
        pass

    def turn_away_mode_on(self):
        """Turn away mode on."""
        pass

    def turn_away_mode_off(self):
        """Turn away mode off."""
        pass

    def turn_fan_on(self):
        """Turn fan on."""
        pass

    def turn_fan_off(self):
        """Turn fan off."""
        pass

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return round(convert(7, TEMP_CELCIUS, self.unit_of_measurement))

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return round(convert(35, TEMP_CELCIUS, self.unit_of_measurement))

    def _convert(self, temp, round_dec=None):
        """Convert temperature into user preferred temperature."""
        if temp is None:
            return None

        value = convert(temp, self.unit_of_measurement,
                        self.hass.config.temperature_unit)

        return value if round_dec is None else round(value, round_dec)
