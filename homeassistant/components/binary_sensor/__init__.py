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

DOMAIN = 'binary_sensor'
DEPENDENCIES = []
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
    """ Represents a binary sensor.. """

    @property
    def is_on(self):
        """ True if the binary sensor is on. """
        return False

    @property
    def friendly_state(self):
        """ Returns the friendly state of the binary sensor. """
        return None
