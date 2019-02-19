"""Support for Mythic Beasts Dynamic DNS service."""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.const import (
    CONF_HOST, CONF_DOMAIN, CONF_PASSWORD, CONF_UPDATE_INTERVAL,
    CONF_SCAN_INTERVAL, CONF_UPDATE_INTERVAL_INVALIDATION_VERSION
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_time_interval

REQUIREMENTS = ['mbddns==0.1.2']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'mythicbeastsdns'

DEFAULT_INTERVAL = timedelta(minutes=10)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.All(
        vol.Schema({
            vol.Required(CONF_DOMAIN): cv.string,
            vol.Required(CONF_HOST): cv.string,
            vol.Required(CONF_PASSWORD): cv.string,
            vol.Optional(CONF_UPDATE_INTERVAL):
                vol.All(cv.time_period, cv.positive_timedelta),
            vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_INTERVAL):
                vol.All(cv.time_period, cv.positive_timedelta),
        }),
        cv.deprecated(
            CONF_UPDATE_INTERVAL,
            replacement_key=CONF_SCAN_INTERVAL,
            invalidation_version=CONF_UPDATE_INTERVAL_INVALIDATION_VERSION,
            default=DEFAULT_INTERVAL
        )
    )
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Initialize the Mythic Beasts component."""
    import mbddns

    domain = config[DOMAIN][CONF_DOMAIN]
    password = config[DOMAIN][CONF_PASSWORD]
    host = config[DOMAIN][CONF_HOST]
    update_interval = config[DOMAIN][CONF_SCAN_INTERVAL]

    session = async_get_clientsession(hass)

    result = await mbddns.update(domain, password, host, session=session)

    if not result:
        return False

    async def update_domain_interval(now):
        """Update the DNS entry."""
        await mbddns.update(domain, password, host, session=session)

    async_track_time_interval(hass, update_domain_interval, update_interval)

    return True
