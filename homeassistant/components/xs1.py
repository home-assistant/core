"""
Support for the EZcontrol XS1 gateway.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/xs1/
"""

import asyncio
import logging
from functools import partial

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers import discovery
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

# Lock used to limit the amount of concurrent update requests
# as the XS1 Gateway can only handle a very small amount of concurrent requests
UPDATE_LOCK = asyncio.Lock()


def _create_controller_api(host, port, ssl, user, password):
    import xs1_api_client
    return xs1_api_client.XS1(
        host=host,
        port=port,
        ssl=ssl,
        user=user,
        password=password)


async def async_setup(hass, config):
    """Set up XS1 Component"""
    _LOGGER.debug("Initializing XS1")

    host = config[DOMAIN].get(CONF_HOST)
    port = config[DOMAIN].get(CONF_PORT)
    ssl = config[DOMAIN].get(CONF_SSL, False)
    user = config[DOMAIN].get(CONF_USERNAME)
    password = config[DOMAIN].get(CONF_PASSWORD)

    # initialize XS1 API

    xs1 = await hass.async_add_executor_job(
        partial(_create_controller_api,
                host, port, ssl, user, password))

    _LOGGER.debug(
        "Establishing connection to XS1 gateway and retrieving data...")

    hass.data[DOMAIN] = {}

    actuators = await hass.async_add_executor_job(partial(xs1.get_all_actuators, enabled=True))
    sensors = await hass.async_add_executor_job(partial(xs1.get_all_sensors, enabled=True))

    hass.data[DOMAIN][ACTUATORS] = actuators
    hass.data[DOMAIN][SENSORS] = sensors

    _LOGGER.debug("loading components for XS1 platform...")
    # load components for supported devices
    for component in XS1_COMPONENTS:
        hass.async_create_task(
            discovery.async_load_platform(
                hass, component, DOMAIN, {}, config))

    return True


class XS1DeviceEntity(Entity):
    """Representation of a base XS1 device."""

    def __init__(self, device):
        """Initialize the XS1 device."""
        self.device = device

    async def async_update(self):
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """

        async with UPDATE_LOCK:
            await self.hass.async_add_executor_job(partial(self.device.update))
