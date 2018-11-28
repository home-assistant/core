"""
NotifyMe platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.notifyme/
"""
import asyncio
import logging
import aiohttp
import async_timeout

import voluptuous as vol

from homeassistant.const import (CONF_NAME, CONF_ACCESS_TOKEN)
from homeassistant.helpers import aiohttp_client
from homeassistant.components.notify import (
    BaseNotificationService, PLATFORM_SCHEMA)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ACCESS_TOKEN): cv.string,
    vol.Optional(CONF_NAME): cv.string,
})

NOTIFYME_API_ENDPOINT = "https://api.notifymyecho.com/v1/NotifyMe"
NOTIFYME_TIMEOUT = 5


def get_service(hass, config, discovery_info=None):
    """Get the NotifyMe notification service."""
    access_token = config[CONF_ACCESS_TOKEN]
    return NotifymeNotificationService(hass, access_token)


class NotifymeNotificationService(BaseNotificationService):
    """Implementation of a notification service for the NotifyMe service."""

    def __init__(self, hass, access_token):
        """Initialize the service."""
        self.hass = hass
        self.access_token = access_token

    async def async_send_message(self, message="", **kwargs):
        """Send a message via NotifyMe."""
        data = {
            "notification": message,
            "accessCode": self.access_token
        }

        try:
            session = aiohttp_client.async_get_clientsession(self.hass)
            with async_timeout.timeout(NOTIFYME_TIMEOUT, loop=self.hass.loop):
                await session.post(NOTIFYME_API_ENDPOINT, json=data)
        except aiohttp.ClientError as err:
            _LOGGER.warning(
                'Error when sending notification: %s', err)
        except asyncio.TimeoutError:
            _LOGGER.warning(
                'Timeout after %d secs', NOTIFYME_TIMEOUT)
