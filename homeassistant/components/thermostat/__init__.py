"""
homeassistant.components.thermostat
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides functionality to interact with thermostats.
"""
import logging
from datetime import timedelta

from homeassistant.helpers import (
    extract_entity_ids, platform_devices_from_config)
import homeassistant.util as util
from homeassistant.helpers import Device
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_TEMPERATURE, ATTR_UNIT_OF_MEASUREMENT,
    STATE_ON, STATE_OFF)

DOMAIN = "thermostat"
ENTITY_ID_FORMAT = DOMAIN + ".{}"

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

DEPENDENCIES = []

SERVICE_SET_AWAY_MODE = "set_away_mode"
SERVICE_SET_TEMPERATURE = "set_temperature"

ATTR_CURRENT_TEMPERATURE = "current_temperature"
ATTR_AWAY_MODE = "away_mode"

_LOGGER = logging.getLogger(__name__)


def turn_away_mode_on(hass, entity_id=None):
    """ Turn all or specified thermostat away mode on. """
    data = {
        ATTR_AWAY_MODE: True
    }

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_SET_AWAY_MODE, data)


def turn_away_mode_off(hass, entity_id=None):
    """ Turn all or specified thermostat away mode off. """
    data = {
        ATTR_AWAY_MODE: False
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

    logger = logging.getLogger(__name__)

    thermostats = platform_devices_from_config(
        config, DOMAIN, hass, ENTITY_ID_FORMAT, _LOGGER)

    if not thermostats:
        return False

    @util.Throttle(MIN_TIME_BETWEEN_SCANS)
    def update_state(now):
        """ Update thermostat state. """
        logger.info("Updating thermostat state")

        for thermostat in thermostats.values():
            if thermostat.should_poll:
                thermostat.update_ha_state(True)

    # Update state every minute
    hass.track_time_change(update_state, second=[0])
    update_state(None)

    def thermostat_service(service):
        """ Handles calls to the services. """

        # Convert the entity ids to valid light ids
        target_thermostats = [thermostats[entity_id] for entity_id
                              in extract_entity_ids(hass, service)
                              if entity_id in thermostats]

        if not target_thermostats:
            target_thermostats = thermostats.values()

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
                thermostat.set_temperature(temperature)

        for thermostat in target_thermostats:
            thermostat.update_ha_state(True)

    hass.services.register(
        DOMAIN, SERVICE_SET_AWAY_MODE, thermostat_service)

    hass.services.register(
        DOMAIN, SERVICE_SET_TEMPERATURE, thermostat_service)

    return True


class ThermostatDevice(Device):
    """ Represents a thermostat within Home Assistant. """

    # pylint: disable=no-self-use

    @property
    def state(self):
        """ Returns the current state. """
        return self.target_temperature

    @property
    def unit_of_measurement(self):
        """ Returns the unit of measurement. """
        return ""

    @property
    def device_state_attributes(self):
        """ Returns device specific state attributes. """
        return None

    @property
    def state_attributes(self):
        """ Returns optional state attributes. """
        data = {
            ATTR_UNIT_OF_MEASUREMENT: self.unit_of_measurement,
            ATTR_CURRENT_TEMPERATURE: self.current_temperature
        }

        is_away = self.is_away_mode_on

        if is_away is not None:
            data[ATTR_AWAY_MODE] = STATE_ON if is_away else STATE_OFF

        device_attr = self.device_state_attributes

        if device_attr is not None:
            data.update(device_attr)

        return data

    @property
    def current_temperature(self):
        """ Returns the current temperature. """
        raise NotImplementedError

    @property
    def target_temperature(self):
        """ Returns the temperature we try to reach. """
        raise NotImplementedError

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
