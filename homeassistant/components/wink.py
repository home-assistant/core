"""
Connects to a Wink hub and loads relevant components to control its devices.
"""
import logging

# pylint: disable=no-name-in-module, import-error
import homeassistant.external.wink.pywink as pywink

from homeassistant import bootstrap
from homeassistant.loader import get_component
from homeassistant.helpers import validate_config, ToggleDevice, Device
from homeassistant.const import (
    EVENT_PLATFORM_DISCOVERED, CONF_ACCESS_TOKEN,
    STATE_OPEN, STATE_CLOSED,
    ATTR_SERVICE, ATTR_DISCOVERED, ATTR_FRIENDLY_NAME)

DOMAIN = "wink"
DEPENDENCIES = []

DISCOVER_LIGHTS = "wink.lights"
DISCOVER_SWITCHES = "wink.switches"
DISCOVER_SENSORS = "wink.sensors"


def setup(hass, config):
    """ Sets up the Wink component. """
    logger = logging.getLogger(__name__)

    if not validate_config(config, {DOMAIN: [CONF_ACCESS_TOKEN]}, logger):
        return False

    pywink.set_bearer_token(config[DOMAIN][CONF_ACCESS_TOKEN])

    # Load components for the devices in the Wink that we support
    for component_name, func_exists, discovery_type in (
            ('light', pywink.get_bulbs, DISCOVER_LIGHTS),
            ('switch', pywink.get_switches, DISCOVER_SWITCHES),
            ('sensor', pywink.get_sensors, DISCOVER_SENSORS)):

        if func_exists():
            component = get_component(component_name)

            # Ensure component is loaded
            if component.DOMAIN not in hass.components:
                bootstrap.setup_component(hass, component.DOMAIN, config)

            # Fire discovery event
            hass.bus.fire(EVENT_PLATFORM_DISCOVERED, {
                ATTR_SERVICE: discovery_type,
                ATTR_DISCOVERED: {}
            })

    return True


class WinkSensorDevice(Device):
    """ represents a wink sensor within home assistant. """

    def __init__(self, wink):
        self.wink = wink

    @property
    def state(self):
        """ Returns the state. """
        return STATE_OPEN if self.is_open else STATE_CLOSED

    @property
    def unique_id(self):
        """ Returns the id of this wink switch """
        return "{}.{}".format(self.__class__, self.wink.deviceId())

    @property
    def name(self):
        """ Returns the name of the sensor if any. """
        return self.wink.name()

    @property
    def state_attributes(self):
        """ Returns optional state attributes. """
        return {
            ATTR_FRIENDLY_NAME: self.wink.name()
        }

    def update(self):
        """ Update state of the sensor. """
        self.wink.updateState()

    @property
    def is_open(self):
        """ True if door is open. """
        return self.wink.state()


class WinkToggleDevice(ToggleDevice):
    """ represents a Wink switch within home assistant. """

    def __init__(self, wink):
        self.wink = wink

    @property
    def unique_id(self):
        """ Returns the id of this WeMo switch """
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
        self.wink.wait_till_desired_reached()
