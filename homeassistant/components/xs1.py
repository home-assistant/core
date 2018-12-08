"""
Support for the EZcontrol XS1 gateway.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/xs1/
"""

import asyncio
import logging

import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['xs1-api-client==2.3.4']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'xs1'
ACTUATORS = 'actuators'
SENSORS = 'sensors'

# configuration keys
CONF_SSL = 'ssl'

# define configuration parameters
CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT): cv.string,
        vol.Optional(CONF_SSL): cv.boolean,
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string
    }),
}, extra=vol.ALLOW_EXTRA)

XS1_COMPONENTS = [
    'switch',
    'sensor',
    'climate'
]


def setup(hass, config):
    """Set up XS1 Component"""
    _LOGGER.debug("Initializing XS1")

    host = config[DOMAIN].get(CONF_HOST)
    port = config[DOMAIN].get(CONF_PORT)
    ssl = config[DOMAIN].get(CONF_SSL, False)
    user = config[DOMAIN].get(CONF_USERNAME)
    password = config[DOMAIN].get(CONF_PASSWORD)

    # initialize XS1 API
    import xs1_api_client
    xs1 = xs1_api_client.XS1(
        host=host,
        port=port,
        ssl=ssl,
        user=user,
        password=password
    )

    _LOGGER.debug(
        "Establishing connection to XS1 gateway and retrieving data...")

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][ACTUATORS] = xs1.get_all_actuators()
    hass.data[DOMAIN][SENSORS] = xs1.get_all_sensors()

    _LOGGER.debug("loading components for XS1 platform...")
    # load components for supported devices
    for component in XS1_COMPONENTS:
        discovery.load_platform(hass, component, DOMAIN, {}, config)

    return True


class XS1DeviceEntity(Entity):
    """Representation of a base XS1 device."""

    def __init__(self, device):
        """Initialize the XS1 device."""
        self.device = device

    @asyncio.coroutine
    def async_update(self):
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        self.device.update()
