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

SERVICE_TURN_AWAY_MODE_ON = "turn_away_mode_on"
SERVICE_TURN_AWAY_MODE_OFF = "turn_away_mode_off"
SERVICE_SET_TEMPERATURE = "set_temperature"

ATTR_TARGET_TEMPERATURE = "target_temperature"
ATTR_AWAY_MODE = "away_mode"

_LOGGER = logging.getLogger(__name__)


def turn_away_mode_on(hass, entity_id=None):
    """ Turn all or specified thermostat away mode on. """
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None

    hass.services.call(DOMAIN, SERVICE_TURN_AWAY_MODE_ON, data)


def turn_away_mode_off(hass, entity_id=None):
    """ Turn all or specified thermostat away mode off. """
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None

    hass.services.call(DOMAIN, SERVICE_TURN_AWAY_MODE_OFF, data)


def set_temperature(hass, temperature, entity_id=None):
    """ Set new target temperature. """
    data = {ATTR_TEMPERATURE: temperature}

    if entity_id is not None:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_SET_TEMPERATURE, data)


def setup(hass, config):
    """ Setup thermostats. """

    thermostats = platform_devices_from_config(
        config, DOMAIN, hass, ENTITY_ID_FORMAT, _LOGGER)

    if not thermostats:
        return False

    # pylint: disable=unused-argument
    @util.Throttle(MIN_TIME_BETWEEN_SCANS)
    def update_state(now):
        """ Update thermostat state. """
        logging.getLogger(__name__).info("Update nest state")

        for thermostat in thermostats.values():
            thermostat.update_ha_state(hass, True)

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

        if service.service == SERVICE_TURN_AWAY_MODE_ON:
            for thermostat in target_thermostats:
                thermostat.turn_away_mode_on()

        elif service.service == SERVICE_TURN_AWAY_MODE_OFF:
            for thermostat in target_thermostats:
                thermostat.turn_away_mode_off()

        elif service.service == SERVICE_SET_TEMPERATURE:
            temperature = util.convert(
                service.data.get(ATTR_TEMPERATURE), float)

            if temperature is None:
                return

            for thermostat in target_thermostats:
                thermostat.nest.set_temperature(temperature)

        for thermostat in target_thermostats:
            thermostat.update_ha_state(hass, True)

    hass.services.register(
        DOMAIN, SERVICE_TURN_AWAY_MODE_OFF, thermostat_service)

    hass.services.register(
        DOMAIN, SERVICE_TURN_AWAY_MODE_ON, thermostat_service)

    hass.services.register(
        DOMAIN, SERVICE_SET_TEMPERATURE, thermostat_service)

    return True


class ThermostatDevice(Device):
    """ Represents a thermostat within Home Assistant. """

    # pylint: disable=no-self-use

    def set_temperate(self, temperature):
        """ Set new target temperature. """
        pass

    def turn_away_mode_on(self):
        """ Turns away mode on. """
        pass

    def turn_away_mode_off(self):
        """ Turns away mode off. """
        pass

    def is_away_mode_on(self):
        """ Returns if away mode is on. """
        return False

    def get_target_temperature(self):
        """ Returns the temperature we try to reach. """
        return None

    def get_unit_of_measurement(self):
        """ Returns the unit of measurement. """
        return ""

    def get_device_state_attributes(self):
        """ Returns device specific state attributes. """
        return {}

    def get_state_attributes(self):
        """ Returns optional state attributes. """
        data = {
            ATTR_UNIT_OF_MEASUREMENT: self.get_unit_of_measurement(),
            ATTR_AWAY_MODE: STATE_ON if self.is_away_mode_on() else STATE_OFF
        }

        target_temp = self.get_target_temperature()

        if target_temp is not None:
            data[ATTR_TARGET_TEMPERATURE] = target_temp

        return data
