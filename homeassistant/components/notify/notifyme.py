"""
NotifyMe platform for notify component.

NotifyMe is an Alexa Skill which allows you to send any message to your
Amazon Echo devices via a simple REST API.

You have to install and set up the skill first to acquire an access code
before you can set up this platform. See http://www.thomptronics.com/notify-me
for instructions.
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
