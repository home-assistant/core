"""
Integrate with DuckDNS.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/duckdns/
"""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.const import CONF_ACCESS_TOKEN, CONF_DOMAIN
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

ATTR_TXT = 'txt'

DOMAIN = 'duckdns'

INTERVAL = timedelta(minutes=5)

SERVICE_SET_TXT = 'set_txt'

UPDATE_URL = 'https://www.duckdns.org/update'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_DOMAIN): cv.string,
        vol.Required(CONF_ACCESS_TOKEN): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)

SERVICE_TXT_SCHEMA = vol.Schema({
    vol.Required(ATTR_TXT): vol.Any(None, cv.string)
})


async def async_setup(hass, config):
    """Initialize the DuckDNS component."""
    domain = config[DOMAIN][CONF_DOMAIN]
    token = config[DOMAIN][CONF_ACCESS_TOKEN]
    session = async_get_clientsession(hass)

    result = await _update_duckdns(session, domain, token)

    if not result:
        return False

    async def update_domain_interval(now):
        """Update the DuckDNS entry."""
        await _update_duckdns(session, domain, token)

    async def update_domain_service(call):
        """Update the DuckDNS entry."""
        await _update_duckdns(
            session, domain, token, txt=call.data[ATTR_TXT])

    async_track_time_interval(hass, update_domain_interval, INTERVAL)
    hass.services.async_register(
        DOMAIN, SERVICE_SET_TXT, update_domain_service,
        schema=SERVICE_TXT_SCHEMA)

    return result


_SENTINEL = object()


async def _update_duckdns(session, domain, token, *, txt=_SENTINEL,
                          clear=False):
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

    resp = await session.get(UPDATE_URL, params=params)
    body = await resp.text()

    if body != 'OK':
        _LOGGER.warning("Updating DuckDNS domain failed: %s", domain)
        return False

    return True
