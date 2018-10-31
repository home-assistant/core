"""
Prowl notification service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.prowl/
"""
import logging
import asyncio

import async_timeout
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_TITLE, ATTR_TITLE_DEFAULT, ATTR_DATA, PLATFORM_SCHEMA,
    BaseNotificationService)
from homeassistant.const import CONF_API_KEY
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)
_RESOURCE = 'https://api.prowlapp.com/publicapi/'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
})


@asyncio.coroutine
def async_get_service(hass, config, discovery_info=None):
    """Get the Prowl notification service."""
    return ProwlNotificationService(hass, config[CONF_API_KEY])


class ProwlNotificationService(BaseNotificationService):
    """Implement the notification service for Prowl."""

    def __init__(self, hass, api_key):
        """Initialize the service."""
        self._hass = hass
        self._api_key = api_key

    @asyncio.coroutine
    def async_send_message(self, message, **kwargs):
        """Send the message to the user."""
        response = None
        session = None
        url = '{}{}'.format(_RESOURCE, 'add')
        data = kwargs.get(ATTR_DATA)
        payload = {
            'apikey': self._api_key,
            'application': 'Home-Assistant',
            'event': kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT),
            'description': message,
            'priority': data['priority'] if data and 'priority' in data else 0
        }

        _LOGGER.debug("Attempting call Prowl service at %s", url)
        session = async_get_clientsession(self._hass)

        try:
            with async_timeout.timeout(10, loop=self._hass.loop):
                response = yield from session.post(url, data=payload)
                result = yield from response.text()

            if response.status != 200 or 'error' in result:
                _LOGGER.error("Prowl service returned http "
                              "status %d, response %s",
                              response.status, result)
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout accessing Prowl at %s", url)
