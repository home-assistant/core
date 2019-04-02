"""Cisco Webex Teams notify component."""
import logging

import voluptuous as vol

from homeassistant.components.notify import (
    PLATFORM_SCHEMA, BaseNotificationService, ATTR_TITLE)
from homeassistant.const import (CONF_TOKEN)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['webexteamssdk==1.1.1']

_LOGGER = logging.getLogger(__name__)

CONF_ROOM_ID = 'room_id'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_TOKEN): cv.string,
    vol.Required(CONF_ROOM_ID): cv.string,
})


def get_service(hass, config, discovery_info=None):
    """Get the CiscoWebexTeams notification service."""

    from webexteamssdk import WebexTeamsAPI
    client = WebexTeamsAPI(access_token=config[CONF_TOKEN])
    # Validate the token by calling an api
    # pylint:disable=expression-not-assigned
    [room for room in client.rooms.list()]

    return CiscoWebexTeamsNotificationService(
        client,
        config[CONF_ROOM_ID])


class CiscoWebexTeamsNotificationService(BaseNotificationService):
    """The Cisco Webex Teams Notification Service."""

    def __init__(self, client, room):
        """Initialize the service."""
        self.room = room
        self.client = client

    def send_message(self, message="", **kwargs):
        """Send a message to a user."""
        from webexteamssdk import ApiError
        try:
            title = ""
            if kwargs.get(ATTR_TITLE) is not None:
                title = "{}{}".format(kwargs.get(ATTR_TITLE), "<br>")
            self.client.messages.create(
                roomId=self.room,
                html="{}{}".format(title, message))
        except ApiError as api_error:
            _LOGGER.error("Could not send CiscoWebexTeams notification. "
                          "Error: %s",
                          api_error)
