"""Cisco Webex Teams notify component."""
import logging

import voluptuous as vol
from webexteamssdk import ApiError, WebexTeamsAPI, exceptions

from homeassistant.components.notify import (
    ATTR_TITLE,
    PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.const import CONF_TOKEN
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_ROOM_ID = "room_id"
CONF_EMAIL = "email"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_TOKEN): cv.string,
        vol.Optional(CONF_ROOM_ID): cv.string,
        vol.Optional(CONF_EMAIL): cv.string,
    }
)


def get_service(hass, config, discovery_info=None):
    """Get the CiscoWebexTeams notification service."""

    client = WebexTeamsAPI(access_token=config[CONF_TOKEN])
    room_or_email = None
    try:
        # Validate the token & room_id
        if CONF_ROOM_ID in config.keys():
            client.rooms.get(config[CONF_ROOM_ID])
            room_or_email = config[CONF_ROOM_ID]
        elif CONF_EMAIL in config.keys():
            room_or_email = config[CONF_EMAIL]
    except exceptions.ApiError as error:
        _LOGGER.error(error)
        return None

    if not room_or_email:
        _LOGGER.error("Please specify either room_id or email")
        return None

    return CiscoWebexTeamsNotificationService(client, room_or_email)


class CiscoWebexTeamsNotificationService(BaseNotificationService):
    """The Cisco Webex Teams Notification Service."""

    def __init__(self, client, room_or_email):
        """Initialize the service."""
        self.room_or_email = room_or_email
        self.client = client

    def send_message(self, message="", **kwargs):
        """Send a message to a user."""

        title = ""
        if kwargs.get(ATTR_TITLE) is not None:
            title = f"{kwargs.get(ATTR_TITLE)}<br>"

        try:
            if "@" in self.room_or_email:
                self.client.messages.create(
                    toPersonEmail=self.room_or_email, html=f"{title}{message}"
                )
            else:
                self.client.messages.create(
                    roomId=self.room_or_email, html=f"{title}{message}"
                )
        except ApiError as api_error:
            _LOGGER.error(
                "Could not send CiscoWebexTeams notification. Error: %s", api_error
            )
