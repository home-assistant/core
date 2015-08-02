"""
homeassistant.components.controller
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Component to interface with various controllers that may control many devices.
For example the Vera Z-Wave controller, Ninja Block, Ninja Sphere etc.
"""
import logging

from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity import Entity

DOMAIN = 'controller'
DEPENDENCIES = ['sensor', 'switch', 'light']
DISCOVERY_PLATFORMS = {}
SCAN_INTERVAL = 30

def setup(hass, config):
    """ Track states and offer events for sensors. """
    component = EntityComponent(
        logging.getLogger(__name__), DOMAIN, hass, SCAN_INTERVAL,
        DISCOVERY_PLATFORMS)

    component.setup(config)

    return True


class Controller(Entity):
	pass
