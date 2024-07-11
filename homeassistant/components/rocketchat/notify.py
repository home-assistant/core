"""Rocket.Chat notification service."""

from __future__ import annotations

from http import HTTPStatus
import logging

from rocketchat_API.APIExceptions.RocketExceptions import (
    RocketAuthenticationException,
    RocketConnectionException,
)
from rocketchat_API.rocketchat import RocketChat
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    PLATFORM_SCHEMA as NOTIFY_PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.const import CONF_PASSWORD, CONF_ROOM, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = NOTIFY_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_URL): vol.Url(),
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_ROOM): cv.string,
    }
)


def get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> RocketChatNotificationService | None:
    """Return the notify service."""

    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    url = config.get(CONF_URL)
    room = config.get(CONF_ROOM)

    try:
        return RocketChatNotificationService(url, username, password, room)
    except RocketConnectionException:
        _LOGGER.warning("Unable to connect to Rocket.Chat server at %s", url)
    except RocketAuthenticationException:
        _LOGGER.warning("Rocket.Chat authentication failed for user %s", username)
        _LOGGER.info("Please check your username/password")

    return None


class RocketChatNotificationService(BaseNotificationService):
    """Implement the notification service for Rocket.Chat."""

    def __init__(self, url, username, password, room):
        """Initialize the service."""

        self._room = room
        self._server = RocketChat(username, password, server_url=url)

    def send_message(self, message="", **kwargs):
        """Send a message to Rocket.Chat."""
        data = kwargs.get(ATTR_DATA) or {}
        resp = self._server.chat_post_message(message, channel=self._room, **data)
        if resp.status_code == HTTPStatus.OK:
            if not resp.json()["success"]:
                _LOGGER.error("Unable to post Rocket.Chat message")
        else:
            _LOGGER.error(
                "Incorrect status code when posting message: %d", resp.status_code
            )
