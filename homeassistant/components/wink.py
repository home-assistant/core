"""
Connects to a Wink hub and loads relevant components to control its devices.
"""
import logging

# pylint: disable=no-name-in-module, import-error
import homeassistant.external.wink.pywink as pywink

from homeassistant import bootstrap
from homeassistant.loader import get_component
from homeassistant.helpers import validate_config
from homeassistant.const import (
    EVENT_SERVICE_DISCOVERED, ATTR_SERVICE, ATTR_DISCOVERED, CONF_ACCESS_TOKEN)

DOMAIN = "wink"
DEPENDENCIES = []

DISCOVER_LIGHTS = "wink.lights"
DISCOVER_SWITCHES = "wink.switches"


def setup(hass, config):
    """ Sets up the Wink component. """
    logger = logging.getLogger(__name__)

    print(config)

    if not validate_config(config, {DOMAIN: [CONF_ACCESS_TOKEN]}, logger):
        return False

    pywink.set_bearer_token(config[DOMAIN][CONF_ACCESS_TOKEN])

    # Load components for the devices in the Wink that we support
    for component_name, func_exists, discovery_type in (
            ('light', pywink.get_bulbs, DISCOVER_LIGHTS),
            ('switch', pywink.get_switches, DISCOVER_SWITCHES)):

        if func_exists():
            component = get_component(component_name)

            # Ensure component is loaded
            if component.DOMAIN not in hass.components:
                # Add a worker on succesfull setup
                if bootstrap.setup_component(hass, component.DOMAIN, config):
                    hass.pool.add_worker()

            # Fire discovery event
            hass.bus.fire(EVENT_SERVICE_DISCOVERED, {
                ATTR_SERVICE: discovery_type,
                ATTR_DISCOVERED: {}
            })

    return True
