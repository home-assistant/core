"""
NotifyMe platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.notifyme/
"""
import logging
import aiohttp

import voluptuous as vol

from homeassistant.const import (CONF_NAME, CONF_ACCESS_TOKEN)
from homeassistant.components.notify import (
    BaseNotificationService, PLATFORM_SCHEMA)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ACCESS_TOKEN): cv.string,
    vol.Optional(CONF_NAME): cv.string,
})

NOTIFYME_API_ENDPOINT = "https://api.notifymyecho.com/v1/NotifyMe"

def get_service(hass, config, discovery_info=None):
    """Get the NotifyMe notification service."""
    accessToken = config[CONF_ACCESS_TOKEN]
    return NotifymeNotificationService(accessToken)

class NotifymeNotificationService(BaseNotificationService):
    """Implementation of a notification service for the NotifyMe service."""

    def __init__(self, accessToken):
        """Initialize the service."""
        self.accessToken = accessToken

    async def async_send_message(self, message="", **kwargs):
        """Send a message via NotifyMe."""
        data = {
            "notification": message,
            "accessCode": self.accessToken
        }

        async with aiohttp.ClientSession() as session:
            await session.post(NOTIFYME_API_ENDPOINT, json=data)
