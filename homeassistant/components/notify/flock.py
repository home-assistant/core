"""
Flock platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.flock/
"""
import asyncio
import logging

import async_timeout
import voluptuous as vol

from homeassistant.components.notify import (
    PLATFORM_SCHEMA, BaseNotificationService)
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)
_RESOURCE = 'https://api.flock.com/hooks/sendMessage/'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ACCESS_TOKEN): cv.string,
})


async def get_service(hass, config, discovery_info=None):
    """Get the Flock.io notification service."""
    access_token = config.get(CONF_ACCESS_TOKEN)
    url = '{}{}'.format(_RESOURCE, access_token)

    return FlockNotificationService(hass, url)


class FlockNotificationService(BaseNotificationService):
    """Implement the notification service for Flock."""

    def __init__(self, hass, url):
        """Initialize the Flock.io notification service."""
        self._hass = hass
        self._url = url

    @asyncio.coroutine
    def async_send_message(self, message, **kwargs):
        """Send the message to the user."""
        payload = {'text': message}

        _LOGGER.debug("Attempting to call Flock at %s", self._url)
        session = async_get_clientsession(self._hass)

        try:
            with async_timeout.timeout(10, loop=self._hass.loop):
                response = yield from session.post(self._url, json=payload)
                result = yield from response.json()

            if response.status != 200 or 'error' in result:
                _LOGGER.error(
                    "Flock service returned HTTP status %d, response %s",
                    response.status, result)
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout accessing Flock at %s", self._url)
