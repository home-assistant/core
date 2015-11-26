"""
homeassistant.components.binary_sensor
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Component to interface with binary sensors (sensors which only know two states)
that can be monitored.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/binary_sensor/
"""
import logging

from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity import Entity
from homeassistant.const import (STATE_ON, STATE_OFF)

DOMAIN = 'binary_sensor'
SCAN_INTERVAL = 30

ENTITY_ID_FORMAT = DOMAIN + '.{}'


def setup(hass, config):
    """ Track states and offer events for binary sensors. """
    component = EntityComponent(
        logging.getLogger(__name__), DOMAIN, hass, SCAN_INTERVAL)

    component.setup(config)

    return True


# pylint: disable=no-self-use
class BinarySensorDevice(Entity):
    """ Represents a binary sensor. """

    @property
    def is_on(self):
        """ True if the binary sensor is on. """
        return None

    @property
    def state(self):
        """ Returns the state of the binary sensor. """
        return STATE_ON if self.is_on else STATE_OFF

    @property
    def friendly_state(self):
        """ Returns the friendly state of the binary sensor. """
        return None
