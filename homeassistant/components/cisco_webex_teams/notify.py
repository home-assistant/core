"""Cisco Webex Teams notify component."""
import logging

import voluptuous as vol
from webexteamssdk import ApiError, WebexTeamsAPI, exceptions

from homeassistant.components.notify import (
    ATTR_TITLE,
    PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.const import CONF_TOKEN, CONF_EMAIL
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_ROOM_ID = "room_id"

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
    room = config.get(CONF_ROOM_ID)
    email = config.get(CONF_EMAIL)

    try:
        # Validate the token & room_id
        if room is not None:
            client.rooms.get(room)
        else:  # there is no room id -> just check if the token is valid.
            client.people.me()

    except exceptions.ApiError as error:
        _LOGGER.error(error)
        return None

    if not room and not email:
        _LOGGER.error("Please specify room_id and/or email address")
        return None

    return CiscoWebexTeamsNotificationService(client, room, email)


class CiscoWebexTeamsNotificationService(BaseNotificationService):
    """The Cisco Webex Teams Notification Service."""

    def __init__(self, client, room, email):
        """Initialize the service."""
        self.room = room
        self.email = email
        self.client = client

    def send_message(self, message="", **kwargs):
        """Send a message to a user."""

        title = ""
        if kwargs.get(ATTR_TITLE) is not None:
            title = f"{kwargs.get(ATTR_TITLE)}<br>"

        try:
            if self.email:
                self.client.messages.create(
                    toPersonEmail=self.email, html=f"{title}{message}"
                )
            if self.room:
                self.client.messages.create(roomId=self.room, html=f"{title}{message}")

        except ApiError as api_error:
            _LOGGER.error(
                "Could not send CiscoWebexTeams notification. Error: %s", api_error
            )
