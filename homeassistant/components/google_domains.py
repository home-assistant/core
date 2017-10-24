"""
Integrate with Google Domains.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/google_domains/
"""
import asyncio
import logging
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_DOMAIN, CONF_PASSWORD, CONF_USERNAME

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'google_domains'

INTERVAL = timedelta(minutes=5)

UPDATE_URL = 'https://{}:{}@domains.google.com/nic/update'

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

    session = hass.helpers.aiohttp_client.async_get_clientsession()

    result = yield from _update_google_domains(session, domain, user, password)

    if not result:
        return False

    @asyncio.coroutine
    def update_domain_interval(now):
        """Update the Google Domains entry."""
        yield from _update_google_domains(session, domain, user, password)

    hass.helpers.event.async_track_time_interval(
        update_domain_interval, INTERVAL)

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

    if not body.startswith('good') and not body.startswith('nochg'):
        _LOGGER.warning('Updating Google Domains domain failed: %s => %s',
                        domain, body)
        return False

    return True
