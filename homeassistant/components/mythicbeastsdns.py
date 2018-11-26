"""
Integrate with Mythic Beasts Dynamic DNS service.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/mythicbeastsdns/
"""
from datetime import timedelta
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_HOST, CONF_DOMAIN, CONF_PASSWORD
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'mythicbeastsdns'

DEFAULT_INTERVAL = timedelta(minutes=10)

UPDATE_URL = 'https://dnsapi4.mythic-beasts.com/'

CONF_UPDATE_INTERVAL = 'update_interval'

TIMEOUT = 20

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_DOMAIN): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_UPDATE_INTERVAL, default=DEFAULT_INTERVAL): vol.All(
            cv.time_period, cv.positive_timedelta),
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Initialize the Mythic Beasts component."""
    domain = config[DOMAIN][CONF_DOMAIN]
    password = config[DOMAIN][CONF_PASSWORD]
    host = config[DOMAIN][CONF_HOST]
    update_interval = config[DOMAIN][CONF_UPDATE_INTERVAL]

    session = async_get_clientsession(hass)

    result = await _update_mythicbeastsdns(session, domain, password, host)

    if not result:
        return False

    async def update_domain_interval(now):
        """Update the DNS entry."""
        await _update_mythicbeastsdns(session, domain, password, host)

    async_track_time_interval(hass, update_domain_interval, update_interval)

    return True


async def _update_mythicbeastsdns(session, domain, password, host):
    """Update Mythic Beasts."""
    data = {
        'domain': domain,
        'password': password,
        'command': "REPLACE {} 5 A DYNAMIC_IP".format(host)
    }

    try:
        resp = await session.post(UPDATE_URL, data=data, timeout=TIMEOUT)
        body = await resp.text()

        if body.startswith("REPLACE"):
            _LOGGER.debug("Updating Mythic Beasts successful: %s", body)
            return True

        if body.startswith("ERR"):
            _LOGGER.error("Updating Mythic Beasts failed: %s",
                          body.partition(' ')[2])

        if body.startswith("NREPLACE"):
            _LOGGER.warning("Updating Mythic Beasts failed: %s",
                            body.partition(';')[2])

    except session.ServerTimeoutError:
        _LOGGER.error("Updating Mythic Beasts failed due to timeout")

    except session.ClientError:
        _LOGGER.error("Updating Mythic Beasts failed.")

    return False
