"""Integrate with NamecheapDNS."""
import asyncio
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_ACCESS_TOKEN, CONF_DOMAIN
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.aiohttp_client import async_get_clientsession

DOMAIN = 'namecheapdns'
UPDATE_URL = 'https://dynamicdns.park-your-domain.com/update'
INTERVAL = timedelta(minutes=5)
_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_DOMAIN): cv.string,
        vol.Required(CONF_ACCESS_TOKEN): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Initialize the NamecheapDNS component."""
    host = config[DOMAIN][CONF_HOST]
    domain = config[DOMAIN][CONF_DOMAIN]
    token = config[DOMAIN][CONF_ACCESS_TOKEN]
    session = async_get_clientsession(hass)

    result = yield from _update_namecheapdns(session, host, domain, token)

    if not result:
        return False

    @asyncio.coroutine
    def update_domain_interval(now):
        """Update the NamecheapDNS entry."""
        yield from _update_namecheapdns(session, host, domain, token)

    async_track_time_interval(hass, update_domain_interval, INTERVAL)

    return result


@asyncio.coroutine
def _update_namecheapdns(session, host, domain, token):
    """Update NamecheapDNS."""
    import xml.etree.ElementTree as ET

    params = {
        'host': host,
        'domain': domain,
        'password': token,
    }

    resp = yield from session.get(UPDATE_URL, params=params)
    xml_string = yield from resp.text()
    root = ET.fromstring(xml_string)
    err_count = root.find('ErrCount').text

    if int(err_count) != 0:
        _LOGGER.warning('Updating Namecheap domain %s failed', domain)
        return False

    return True
