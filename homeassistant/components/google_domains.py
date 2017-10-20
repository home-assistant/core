"""Integrate with Google Domains."""
import asyncio
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.const import CONF_DOMAIN, CONF_PASSWORD, CONF_USERNAME
from homeassistant.loader import bind_hass
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.aiohttp_client import async_get_clientsession

DOMAIN = 'google_domains'
UPDATE_URL = 'https://{}:{}@domains.google.com/nic/update'
INTERVAL = timedelta(minutes=5)
_LOGGER = logging.getLogger(__name__)
SERVICE_UPDATE_DNS = 'update_dns'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_DOMAIN): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string
    })
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Initialize the Google Domains component."""
    domain = config[DOMAIN][CONF_DOMAIN]
    user = config[DOMAIN][CONF_USERNAME]
    password = config[DOMAIN][CONF_PASSWORD]
    session = async_get_clientsession(hass)

    result = yield from _update_google_domains(session, domain, user, password)

    if not result:
        return False

    @asyncio.coroutine
    def update_domain_interval(now):
        """Update the Google Domains entry."""
        yield from _update_google_domains(session, domain, user, password)

    @asyncio.coroutine
    def update_domain_service(call):
        """Update the Google Domains entry."""
        yield from _update_google_domains(session, domain, user, password)

    async_track_time_interval(hass, update_domain_interval, INTERVAL)
    hass.services.async_register(DOMAIN, SERVICE_UPDATE_DNS, update_domain_service)

    return result


@asyncio.coroutine
def _update_google_domains(session, domain, user, password):
    """Update Google Domains."""
    url = UPDATE_URL.format(user, password)
    
    params = {
        'hostname': domain
    }

    resp = yield from session.get(url, params=params)
    body = yield from resp.text()
    
    _LOGGER.debug(body)

    if not body.startswith('good') and not body.startswith('nochg'):
        _LOGGER.warning('Updating Google Domains domain %s failed: %s', domain)
        return False

    return True
