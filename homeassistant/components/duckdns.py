"""Integrate with DuckDNS."""
import asyncio
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.const import CONF_ACCESS_TOKEN, CONF_DOMAIN
from homeassistant.loader import bind_hass
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.aiohttp_client import async_get_clientsession

DOMAIN = 'duckdns'
UPDATE_URL = 'https://www.duckdns.org/update'
INTERVAL = timedelta(minutes=5)
_LOGGER = logging.getLogger(__name__)
SERVICE_SET_TXT = 'set_txt'
ATTR_TXT = 'txt'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_DOMAIN): cv.string,
        vol.Required(CONF_ACCESS_TOKEN): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)

SERVICE_TXT_SCHEMA = vol.Schema({
    vol.Required(ATTR_TXT): vol.Any(None, cv.string)
})


@bind_hass
@asyncio.coroutine
def async_set_txt(hass, txt):
    """Set the txt record. Pass in None to remove it."""
    yield from hass.services.async_call(DOMAIN, SERVICE_SET_TXT, {
        ATTR_TXT: txt
    }, blocking=True)


@asyncio.coroutine
def async_setup(hass, config):
    """Initialize the DuckDNS component."""
    domain = config[DOMAIN][CONF_DOMAIN]
    token = config[DOMAIN][CONF_ACCESS_TOKEN]
    session = async_get_clientsession(hass)

    result = yield from _update_duckdns(session, domain, token)

    if not result:
        return False

    @asyncio.coroutine
    def update_domain_interval(now):
        """Update the DuckDNS entry."""
        yield from _update_duckdns(session, domain, token)

    @asyncio.coroutine
    def update_domain_service(call):
        """Update the DuckDNS entry."""
        yield from _update_duckdns(session, domain, token,
                                   txt=call.data[ATTR_TXT])

    async_track_time_interval(hass, update_domain_interval, INTERVAL)
    hass.services.async_register(
        DOMAIN, SERVICE_SET_TXT, update_domain_service,
        schema=SERVICE_TXT_SCHEMA)

    return result


_SENTINEL = object()


@asyncio.coroutine
def _update_duckdns(session, domain, token, *, txt=_SENTINEL, clear=False):
    """Update DuckDNS."""
    params = {
        'domains': domain,
        'token': token,
    }

    if txt is not _SENTINEL:
        if txt is None:
            # Pass in empty txt value to indicate it's clearing txt record
            params['txt'] = ''
            clear = True
        else:
            params['txt'] = txt

    if clear:
        params['clear'] = 'true'

    resp = yield from session.get(UPDATE_URL, params=params)
    body = yield from resp.text()

    if body != 'OK':
        _LOGGER.warning('Updating DuckDNS domain %s failed', domain)
        return False

    return True
