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

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_TOKEN): cv.string, vol.Required(CONF_ROOM_ID): cv.string}
)


def get_service(hass, config, discovery_info=None):
    """Get the CiscoWebexTeams notification service."""

    client = WebexTeamsAPI(access_token=config[CONF_TOKEN])
    try:
        # Validate the token & room_id
        client.rooms.get(config[CONF_ROOM_ID])
    except exceptions.ApiError as error:
        _LOGGER.error(error)
        return None

    return CiscoWebexTeamsNotificationService(client, config[CONF_ROOM_ID])


class CiscoWebexTeamsNotificationService(BaseNotificationService):
    """The Cisco Webex Teams Notification Service."""

    def __init__(self, client, room):
        """Initialize the service."""
        self.room = room
        self.client = client

    def send_message(self, message="", **kwargs):
        """Send a message to a user."""

        title = ""
        if kwargs.get(ATTR_TITLE) is not None:
            title = f"{kwargs.get(ATTR_TITLE)}<br>"

        try:
            self.client.messages.create(roomId=self.room, html=f"{title}{message}")
        except ApiError as api_error:
            _LOGGER.error(
                "Could not send CiscoWebexTeams notification. Error: %s", api_error
            )
