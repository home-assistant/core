"""
homeassistant.components.controller
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Component to interface with various controllers that may control many devices.
For example the Vera Z-Wave controller, Ninja Block, Ninja Sphere etc.

A controller entity should interrogate its configured device and use the
discovery mechanism to create child entities.
"""
import logging

from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity import Entity

DOMAIN = 'controller'
DEPENDENCIES = ['sensor', 'switch', 'light']
DISCOVERY_PLATFORMS = {}
SCAN_INTERVAL = 30
SERVICE_FORCE_UPDATE = 'force_update'

def setup(hass, config):
    """ Track states and offer events for sensors. """
    component = EntityComponent(
        logging.getLogger(__name__), DOMAIN, hass, SCAN_INTERVAL,
        DISCOVERY_PLATFORMS)

    component.setup(config)

    def force_update(service):
        target_controllers = component.extract_from_service(service)
        """ This service can be called to force a refresh from the
        controller device """
        print('jjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjj')
        print(service)
        for target_controller in target_controllers:
            target_controller.update()
            target_controller.update_ha_state(True)

    hass.services.register(DOMAIN, SERVICE_FORCE_UPDATE, force_update)

    return True


class Controller(Entity):
    """ This is the base class for controller devices """
    @property
    # pylint: disable=no-self-use
    def device_type(self):
        """ A string identifying the controller type,
        eg. VeraLite or NinjaSphere """
        return None

    @property
    # pylint: disable=no-self-use
    def model(self):
        """ The specific model info for the controler """
        return None

    @property
    # pylint: disable=no-self-use
    def version(self):
        """ Should return a version number for the device,
        for example controller firmware version """
        return None
