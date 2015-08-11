"""
components.verisure
~~~~~~~~~~~~~~~~~~
"""
import logging

from homeassistant import bootstrap
from homeassistant.helpers import validate_config
from homeassistant.loader import get_component
from homeassistant.const import (
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP,
    CONF_USERNAME, CONF_PASSWORD,
    EVENT_PLATFORM_DISCOVERED,
    ATTR_SERVICE, ATTR_DISCOVERED, ATTR_FRIENDLY_NAME)

DOMAIN = "verisure"
DEPENDENCIES = []
REQUIREMENTS = ['https://github.com/persandstrom/python-verisure/archive/master.zip']

MY_PAGES = None
_LOGGER = logging.getLogger(__name__)

DISCOVER_SENSORS = "wink.sensors"

def setup(hass, config):
    """ Setup the Verisure component. """

    if not validate_config(config,
                           {DOMAIN: [CONF_USERNAME, CONF_PASSWORD]},
                           _LOGGER):
        return False

    from verisure import MyPages
    global MY_PAGES
    MY_PAGES = MyPages(config[DOMAIN][CONF_USERNAME], config[DOMAIN][CONF_PASSWORD])
    MY_PAGES.login()

    component = get_component('sensor')
    bootstrap.setup_component(hass, component.DOMAIN, config)

    # Fire discovery event
    hass.bus.fire(EVENT_PLATFORM_DISCOVERED, {
        ATTR_SERVICE: DISCOVER_SENSORS,
        ATTR_DISCOVERED: {}
    })

    def stop_verisure(event):
        """ Stop the Arduino service. """
        MY_PAGES.logout()

    def start_verisure(event):
        """ Start the Arduino service. """
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_verisure)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, start_verisure)

    return True
