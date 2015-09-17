"""
homeassistant.components.wink
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Connects to a Wink hub and loads relevant components to control its devices.

Configuration:

To use the Wink component you will need to add something like the following
to your configuration.yaml file.

wink:
  access_token: YOUR_ACCESS_TOKEN

Variables:

access_token
*Required
Please check https://home-assistant.io/components/wink.html for further
details.
"""
import logging

from homeassistant import bootstrap
from homeassistant.loader import get_component
from homeassistant.helpers import validate_config
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.const import (
    EVENT_PLATFORM_DISCOVERED, CONF_ACCESS_TOKEN,
    ATTR_SERVICE, ATTR_DISCOVERED, ATTR_FRIENDLY_NAME)

DOMAIN = "wink"
DEPENDENCIES = []
REQUIREMENTS = ['https://github.com/balloob/python-wink/archive/'
                'c2b700e8ca866159566ecf5e644d9c297f69f257.zip'
                '#python-wink==0.1']

DISCOVER_LIGHTS = "wink.lights"
DISCOVER_SWITCHES = "wink.switches"
DISCOVER_SENSORS = "wink.sensors"


def setup(hass, config):
    """ Sets up the Wink component. """
    logger = logging.getLogger(__name__)

    if not validate_config(config, {DOMAIN: [CONF_ACCESS_TOKEN]}, logger):
        return False

    import pywink
    pywink.set_bearer_token(config[DOMAIN][CONF_ACCESS_TOKEN])

    # Load components for the devices in the Wink that we support
    for component_name, func_exists, discovery_type in (
            ('light', pywink.get_bulbs, DISCOVER_LIGHTS),
            ('switch', pywink.get_switches, DISCOVER_SWITCHES),
            ('sensor', pywink.get_sensors, DISCOVER_SENSORS)):

        if func_exists():
            component = get_component(component_name)

            # Ensure component is loaded
            bootstrap.setup_component(hass, component.DOMAIN, config)

            # Fire discovery event
            hass.bus.fire(EVENT_PLATFORM_DISCOVERED, {
                ATTR_SERVICE: discovery_type,
                ATTR_DISCOVERED: {}
            })

    return True


class WinkToggleDevice(ToggleEntity):
    """ Represents a Wink switch within Home Assistant. """

    def __init__(self, wink):
        self.wink = wink

    @property
    def unique_id(self):
        """ Returns the id of this Wink switch. """
        return "{}.{}".format(self.__class__, self.wink.deviceId())

    @property
    def name(self):
        """ Returns the name of the light if any. """
        return self.wink.name()

    @property
    def is_on(self):
        """ True if light is on. """
        return self.wink.state()

    @property
    def state_attributes(self):
        """ Returns optional state attributes. """
        return {
            ATTR_FRIENDLY_NAME: self.wink.name()
        }

    def turn_on(self, **kwargs):
        """ Turns the switch on. """
        self.wink.setState(True)

    def turn_off(self):
        """ Turns the switch off. """
        self.wink.setState(False)

    def update(self):
        """ Update state of the light. """
        self.wink.updateState()
