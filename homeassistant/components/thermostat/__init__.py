"""
homeassistant.components.thermostat
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
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

STATE_HEAT = "heat"
STATE_COOL = "cool"
STATE_IDLE = "idle"

ATTR_CURRENT_TEMPERATURE = "current_temperature"
ATTR_AWAY_MODE = "away_mode"
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
    """ Turn all or specified thermostat away mode on. """
    data = {
        ATTR_AWAY_MODE: away_mode
    }

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_SET_AWAY_MODE, data)


def set_temperature(hass, temperature, entity_id=None):
    """ Set new target temperature. """
    data = {ATTR_TEMPERATURE: temperature}

    if entity_id is not None:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_SET_TEMPERATURE, data)


def setup(hass, config):
    """ Setup thermostats. """
    component = EntityComponent(_LOGGER, DOMAIN, hass,
                                SCAN_INTERVAL, DISCOVERY_PLATFORMS)
    component.setup(config)

    def thermostat_service(service):
        """ Handles calls to the services. """

        # Convert the entity ids to valid light ids
        target_thermostats = component.extract_from_service(service)

        if service.service == SERVICE_SET_AWAY_MODE:
            away_mode = service.data.get(ATTR_AWAY_MODE)

            if away_mode is None:
                _LOGGER.error(
                    "Received call to %s without attribute %s",
                    SERVICE_SET_AWAY_MODE, ATTR_AWAY_MODE)

            elif away_mode:
                for thermostat in target_thermostats:
                    thermostat.turn_away_mode_on()
            else:
                for thermostat in target_thermostats:
                    thermostat.turn_away_mode_off()

        elif service.service == SERVICE_SET_TEMPERATURE:
            temperature = util.convert(
                service.data.get(ATTR_TEMPERATURE), float)

            if temperature is None:
                return

            for thermostat in target_thermostats:
                thermostat.set_temperature(convert(
                    temperature, hass.config.temperature_unit,
                    thermostat.unit_of_measurement))

        for thermostat in target_thermostats:
            thermostat.update_ha_state(True)

    descriptions = load_yaml_config_file(
        os.path.join(os.path.dirname(__file__), 'services.yaml'))

    hass.services.register(
        DOMAIN, SERVICE_SET_AWAY_MODE, thermostat_service,
        descriptions.get(SERVICE_SET_AWAY_MODE))

    hass.services.register(
        DOMAIN, SERVICE_SET_TEMPERATURE, thermostat_service,
        descriptions.get(SERVICE_SET_TEMPERATURE))

    return True


class ThermostatDevice(Entity):
    """ Represents a thermostat within Home Assistant. """

    # pylint: disable=no-self-use

    @property
    def state(self):
        """ Returns the current state. """
        return self.target_temperature or STATE_UNKNOWN

    @property
    def device_state_attributes(self):
        """ Returns device specific state attributes. """
        return None

    @property
    def state_attributes(self):
        """ Returns optional state attributes. """

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

        device_attr = self.device_state_attributes

        if device_attr is not None:
            data.update(device_attr)

        return data

    @property
    def unit_of_measurement(self):
        """ Unit of measurement this thermostat expresses itself in. """
        raise NotImplementedError

    @property
    def current_temperature(self):
        """ Returns the current temperature. """
        raise NotImplementedError

    @property
    def operation(self):
        """ Returns current operation ie. heat, cool, idle """
        return None

    @property
    def target_temperature(self):
        """ Returns the temperature we try to reach. """
        raise NotImplementedError

    @property
    def target_temperature_low(self):
        """ Returns the lower bound temperature we try to reach. """
        return self.target_temperature

    @property
    def target_temperature_high(self):
        """ Returns the upper bound temperature we try to reach. """
        return self.target_temperature

    @property
    def is_away_mode_on(self):
        """
        Returns if away mode is on.
        Return None if no away mode available.
        """
        return None

    def set_temperate(self, temperature):
        """ Set new target temperature. """
        pass

    def turn_away_mode_on(self):
        """ Turns away mode on. """
        pass

    def turn_away_mode_off(self):
        """ Turns away mode off. """
        pass

    @property
    def min_temp(self):
        """ Return minimum temperature. """
        return convert(7, TEMP_CELCIUS, self.unit_of_measurement)

    @property
    def max_temp(self):
        """ Return maxmum temperature. """
        return convert(35, TEMP_CELCIUS, self.unit_of_measurement)

    def _convert(self, temp, round_dec=None):
        """ Convert temperature from this thermost into user preferred
            temperature. """
        if temp is None:
            return None

        value = convert(temp, self.unit_of_measurement,
                        self.hass.config.temperature_unit)

        return value if round_dec is None else round(value, round_dec)
