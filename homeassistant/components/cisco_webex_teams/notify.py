"""Cisco Webex Teams notify component."""
import logging

import voluptuous as vol

from homeassistant.components.notify import (
    PLATFORM_SCHEMA, BaseNotificationService, ATTR_TITLE)
from homeassistant.const import (CONF_TOKEN)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['webexteamssdk==1.1.1']

_LOGGER = logging.getLogger(__name__)

CONF_ROOMID = 'roomid'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_TOKEN): cv.string,
    vol.Required(CONF_ROOMID): cv.string,
})


def get_service(hass, config, discovery_info=None):
    """Get the CiscoWebexTeams notification service."""
    return CiscoWebexTeamsNotificationService(
        config[CONF_TOKEN],
        config[CONF_ROOMID])


class CiscoWebexTeamsNotificationService(BaseNotificationService):
    """The Cisco Webex Teams Notification Service."""

    def __init__(self, token, room):
        """Initialize the service."""
        from webexteamssdk import WebexTeamsAPI
        self.room = room
        self.client = WebexTeamsAPI(access_token=token)

    def send_message(self, message="", **kwargs):
        """Send a message to a user."""
        from webexteamssdk import ApiError
        try:
            title = ""
            if kwargs.get(ATTR_TITLE) is not None:
                title = "{}{}".format(kwargs.get(ATTR_TITLE), "<br>")
            self.client.messages.create(
                roomId=self.room,
                html=title + message)
        except ApiError as api_error:
            _LOGGER.error("Could not send CiscoWebexTeams notification. "
                          "Error: %s",
                          api_error)
