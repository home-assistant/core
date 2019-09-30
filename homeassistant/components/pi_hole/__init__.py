"""The pi_hole component."""
import logging

import voluptuous as vol
from hole import Hole
from hole.exceptions import HoleError

from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_API_KEY,
    CONF_SSL,
    CONF_VERIFY_SSL,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.util import Throttle

from .const import (
    DOMAIN,
    CONF_LOCATION,
    DEFAULT_HOST,
    DEFAULT_LOCATION,
    DEFAULT_NAME,
    DEFAULT_SSL,
    DEFAULT_VERIFY_SSL,
    MIN_TIME_BETWEEN_UPDATES,
    SERVICE_DISABLE,
    SERVICE_DISABLE_ATTR_DURATION,
    SERVICE_ENABLE,
)

LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                vol.Optional(CONF_API_KEY): cv.string,
                vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
                vol.Optional(CONF_LOCATION, default=DEFAULT_LOCATION): cv.string,
                vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_DISABLE_SCHEMA = vol.Schema(
    {
        vol.Required(SERVICE_DISABLE_ATTR_DURATION): vol.All(
            cv.time_period_str, cv.positive_timedelta
        )
    }
)


async def async_setup(hass, config):
    """Set up the pi_hole integration."""

    conf = config[DOMAIN]
    name = conf[CONF_NAME]
    host = conf[CONF_HOST]
    use_tls = conf[CONF_SSL]
    verify_tls = conf[CONF_VERIFY_SSL]
    location = conf[CONF_LOCATION]
    api_key = conf.get(CONF_API_KEY)

    LOGGER.debug("Setting up %s integration with host %s", DOMAIN, host)

    session = async_get_clientsession(hass, verify_tls)
    pi_hole = PiHoleData(
        Hole(
            host, hass.loop, session, location=location, tls=use_tls, api_token=api_key
        ),
        name,
    )

    await pi_hole.async_update()

    hass.data[DOMAIN] = pi_hole

    async def handle_disable(call):
        if api_key is None:
            raise vol.Invalid("Pi-hole api_key must be provided in configuration")

        duration = call.data[SERVICE_DISABLE_ATTR_DURATION].total_seconds()

        LOGGER.debug("Disabling %s %s for %d seconds", DOMAIN, host, duration)
        await pi_hole.api.disable(duration)

    async def handle_enable(call):
        if api_key is None:
            raise vol.Invalid("Pi-hole api_key must be provided in configuration")

        LOGGER.debug("Enabling %s %s", DOMAIN, host)
        await pi_hole.api.enable()

    hass.services.async_register(
        DOMAIN, SERVICE_DISABLE, handle_disable, schema=SERVICE_DISABLE_SCHEMA
    )

    hass.services.async_register(DOMAIN, SERVICE_ENABLE, handle_enable)

    hass.async_create_task(async_load_platform(hass, SENSOR_DOMAIN, DOMAIN, {}, config))

    return True


class PiHoleData:
    """Get the latest data and update the states."""

    def __init__(self, api, name):
        """Initialize the data object."""
        self.api = api
        self.name = name
        self.available = True

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Get the latest data from the Pi-hole."""

        try:
            await self.api.get_data()
            self.available = True
        except HoleError:
            LOGGER.error("Unable to fetch data from Pi-hole")
            self.available = False
