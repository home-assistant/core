"""
Connects to an ISY-994 controller and loads relevant components to control its devices.
"""
# system imports
import logging
from urllib.parse import urlparse

# addon library imports
import PyISY

# homeassistant imports
from homeassistant import bootstrap
from homeassistant.loader import get_component
from homeassistant.helpers import validate_config
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.const import (
        CONF_HOST, CONF_USERNAME, CONF_PASSWORD,
    EVENT_PLATFORM_DISCOVERED,
    ATTR_SERVICE, ATTR_DISCOVERED, ATTR_FRIENDLY_NAME)

# homeassistant constants
DOMAIN = "isy994"
DEPENDENCIES = []
#DISCOVER_LIGHTS = "isy994.lights"
#DISCOVER_SWITCHES = "isy994.switches"
DISCOVER_SENSORS = "isy994.sensors"
ISY = None

def setup(hass, config):
    """ Sets up the ISY994 component. """
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    # pull values from configuration file
    if not validate_config(config, 
            {DOMAIN: [CONF_HOST, CONF_USERNAME, CONF_PASSWORD]}, logger):
        return False
    else:
        user = config[DOMAIN][CONF_USERNAME]
        password = config[DOMAIN][CONF_PASSWORD]
        host = urlparse(config[DOMAIN][CONF_HOST])
        addr = host.geturl()
        if host.scheme == 'http':
            addr = addr.replace('http://', '')
            https = False
        elif host.scheme == 'https':
            addr = addr.replace('https://', '')
            https = True
        else:
            logger.error('isy994 host value in configuration ' + 
                    'file is invalid.')
            return False
        port = host.port
        addr = addr.replace(':{}'.format(port), '')

    # connect to ISY controller
    global ISY
    ISY = PyISY.ISY(addr, port, user, password, use_https=https, log=logger)
    if not ISY.connected:
        return False

    # Load components for the devices in the ISY controller that we support
    for comp_name, discovery in ((('sensor', DISCOVER_SENSORS),)):
        component = get_component(comp_name)
        bootstrap.setup_component(hass, component.DOMAIN, config)
        hass.bus.fire(EVENT_PLATFORM_DISCOVERED, 
                {
                    ATTR_SERVICE: discovery,
                    ATTR_DISCOVERED: {}
                })

    ISY.auto_update = True
    return True
