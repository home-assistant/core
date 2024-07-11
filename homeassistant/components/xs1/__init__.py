"""Support for the EZcontrol XS1 gateway."""

import asyncio
import logging

import voluptuous as vol
import xs1_api_client

from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "xs1"
ACTUATORS = "actuators"
SENSORS = "sensors"

# define configuration parameters
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Optional(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_PORT, default=80): cv.string,
                vol.Optional(CONF_SSL, default=False): cv.boolean,
                vol.Optional(CONF_USERNAME): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = [Platform.CLIMATE, Platform.SENSOR, Platform.SWITCH]

# Lock used to limit the amount of concurrent update requests
# as the XS1 Gateway can only handle a very
# small amount of concurrent requests
UPDATE_LOCK = asyncio.Lock()


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up XS1 integration."""
    _LOGGER.debug("Initializing XS1")

    host = config[DOMAIN][CONF_HOST]
    port = config[DOMAIN][CONF_PORT]
    ssl = config[DOMAIN][CONF_SSL]
    user = config[DOMAIN].get(CONF_USERNAME)
    password = config[DOMAIN].get(CONF_PASSWORD)

    # initialize XS1 API
    try:
        xs1 = xs1_api_client.XS1(
            host=host, port=port, ssl=ssl, user=user, password=password
        )
    except ConnectionError as error:
        _LOGGER.error(
            "Failed to create XS1 API client because of a connection error: %s",
            error,
        )
        return False

    _LOGGER.debug("Establishing connection to XS1 gateway and retrieving data")

    hass.data[DOMAIN] = {}

    actuators = xs1.get_all_actuators(enabled=True)
    sensors = xs1.get_all_sensors(enabled=True)

    hass.data[DOMAIN][ACTUATORS] = actuators
    hass.data[DOMAIN][SENSORS] = sensors

    _LOGGER.debug("Loading platforms for XS1 integration")
    # Load platforms for supported devices
    for platform in PLATFORMS:
        discovery.load_platform(hass, platform, DOMAIN, {}, config)

    return True


class XS1DeviceEntity(Entity):
    """Representation of a base XS1 device."""

    def __init__(self, device):
        """Initialize the XS1 device."""
        self.device = device

    async def async_update(self):
        """Retrieve latest device state."""
        async with UPDATE_LOCK:
            await self.hass.async_add_executor_job(self.device.update)
