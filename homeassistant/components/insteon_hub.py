"""
Support for Insteon Hub.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/insteon_hub/
"""
import logging

import homeassistant.bootstrap as bootstrap
from homeassistant.const import (
    ATTR_DISCOVERED, ATTR_SERVICE, CONF_API_KEY, CONF_PASSWORD, CONF_USERNAME,
    EVENT_PLATFORM_DISCOVERED)
from homeassistant.helpers import validate_config
from homeassistant.loader import get_component

DOMAIN = "insteon_hub"
REQUIREMENTS = ['insteon_hub==0.4.5']
INSTEON = None
DISCOVER_LIGHTS = "insteon_hub.lights"
_LOGGER = logging.getLogger(__name__)


def setup(hass, config):
    """Setup Insteon Hub component.

    This will automatically import associated lights.
    """
    if not validate_config(
            config,
            {DOMAIN: [CONF_USERNAME, CONF_PASSWORD, CONF_API_KEY]},
            _LOGGER):
        return False

    import insteon

    username = config[DOMAIN][CONF_USERNAME]
    password = config[DOMAIN][CONF_PASSWORD]
    api_key = config[DOMAIN][CONF_API_KEY]

    global INSTEON
    INSTEON = insteon.Insteon(username, password, api_key)

    if INSTEON is None:
        _LOGGER.error("Could not connect to Insteon service.")
        return

    comp_name = 'light'
    discovery = DISCOVER_LIGHTS
    component = get_component(comp_name)
    bootstrap.setup_component(hass, component.DOMAIN, config)
    hass.bus.fire(
        EVENT_PLATFORM_DISCOVERED,
        {ATTR_SERVICE: discovery, ATTR_DISCOVERED: {}})
    return True
