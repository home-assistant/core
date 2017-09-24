"""
Rocket.Chat notification service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.rocketchat/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.const import (
    CONF_URL, CONF_USERNAME, CONF_PASSWORD)
from homeassistant.components.notify import (
    ATTR_DATA, PLATFORM_SCHEMA,
    BaseNotificationService)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['rocketchat-API==0.6.1']

CONF_ROOM = 'room'

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_URL): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_ROOM): cv.string,
})


@asyncio.coroutine
def async_get_service(hass, config, discovery_info=None):
    """Return the notify service."""
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    url = config.get(CONF_URL)
    room = config.get(CONF_ROOM)

    return RocketChatNotificationService(url, username, password, room)


class RocketChatNotificationService(BaseNotificationService):
    """Implement the notification service for Rocket.Chat."""

    def __init__(self, url, username, password, room):
        """Initialize the service."""
        from rocketchat_API.rocketchat import RocketChat
        from rocketchat_API.APIExceptions.RocketExceptions import (
            RocketConnectionException, RocketAuthenticationException)
        self._room = room
        try:
            self._server = RocketChat(username, password, server_url=url)
        except RocketConnectionException:
            _LOGGER.warning(
                "Unable to connect to Rocket.Chat server at %s.", url)
        except RocketAuthenticationException:
            _LOGGER.warning(
                "Rocket.Chat authentication failed for user %s.", username)
            _LOGGER.info("Please check your username/password.")

    @asyncio.coroutine
    def async_send_message(self, message="", **kwargs):
        """Send a message to Rocket.Chat."""
        data = kwargs.get(ATTR_DATA) or {}
        self._server.chat_post_message(message, channel=self._room, **data)
