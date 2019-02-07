"""
Integrate with namecheap DNS services.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/namecheapdns/
"""
import logging
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_DOMAIN
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.aiohttp_client import async_get_clientsession

REQUIREMENTS = ['defusedxml==0.5.0']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'namecheapdns'

INTERVAL = timedelta(minutes=5)

UPDATE_URL = 'https://dynamicdns.park-your-domain.com/update'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_DOMAIN): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_HOST, default='@'): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Initialize the namecheap DNS component."""
    host = config[DOMAIN][CONF_HOST]
    domain = config[DOMAIN][CONF_DOMAIN]
    password = config[DOMAIN][CONF_PASSWORD]

    session = async_get_clientsession(hass)

    result = await _update_namecheapdns(session, host, domain, password)

    if not result:
        return False

    async def update_domain_interval(now):
        """Update the namecheap DNS entry."""
        await _update_namecheapdns(session, host, domain, password)

    async_track_time_interval(hass, update_domain_interval, INTERVAL)

    return result


async def _update_namecheapdns(session, host, domain, password):
    """Update namecheap DNS entry."""
    import defusedxml.ElementTree as ET

    params = {
        'host': host,
        'domain': domain,
        'password': password,
    }

    resp = await session.get(UPDATE_URL, params=params)
    xml_string = await resp.text()
    root = ET.fromstring(xml_string)
    err_count = root.find('ErrCount').text

    if int(err_count) != 0:
        _LOGGER.warning("Updating namecheap domain failed: %s", domain)
        return False

    return True
