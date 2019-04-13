"""Support for the EZcontrol XS1 gateway."""
import asyncio
from functools import partial
import logging

import voluptuous as vol

from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_SSL, CONF_USERNAME)
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'xs1'
ACTUATORS = 'actuators'
SENSORS = 'sensors'

# define configuration parameters
CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_PORT, default=80): cv.string,
        vol.Optional(CONF_SSL, default=False): cv.boolean,
        vol.Optional(CONF_USERNAME): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)

XS1_COMPONENTS = [
    'climate',
    'sensor',
    'switch',
]

# Lock used to limit the amount of concurrent update requests
# as the XS1 Gateway can only handle a very
# small amount of concurrent requests
UPDATE_LOCK = asyncio.Lock()


def _create_controller_api(host, port, ssl, user, password):
    """Create an api instance to use for communication."""
    import xs1_api_client

    try:
        return xs1_api_client.XS1(
            host=host, port=port, ssl=ssl, user=user, password=password)
    except ConnectionError as error:
        _LOGGER.error("Failed to create XS1 API client "
                      "because of a connection error: %s", error)
        return None


async def async_setup(hass, config):
    """Set up XS1 Component."""
    _LOGGER.debug("Initializing XS1")

    host = config[DOMAIN][CONF_HOST]
    port = config[DOMAIN][CONF_PORT]
    ssl = config[DOMAIN][CONF_SSL]
    user = config[DOMAIN].get(CONF_USERNAME)
    password = config[DOMAIN].get(CONF_PASSWORD)

    # initialize XS1 API
    xs1 = await hass.async_add_executor_job(
        partial(_create_controller_api, host, port, ssl, user, password))
    if xs1 is None:
        return False

    _LOGGER.debug(
        "Establishing connection to XS1 gateway and retrieving data...")

    hass.data[DOMAIN] = {}

    actuators = await hass.async_add_executor_job(
        partial(xs1.get_all_actuators, enabled=True))
    sensors = await hass.async_add_executor_job(
        partial(xs1.get_all_sensors, enabled=True))

    hass.data[DOMAIN][ACTUATORS] = actuators
    hass.data[DOMAIN][SENSORS] = sensors

    _LOGGER.debug("Loading components for XS1 platform...")
    # Load components for supported devices
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
        """Retrieve latest device state."""
        async with UPDATE_LOCK:
            await self.hass.async_add_executor_job(
                partial(self.device.update))
