"""Cisco Webex notify component."""

from __future__ import annotations

import logging

import voluptuous as vol
from webexpythonsdk import ApiError, WebexAPI, exceptions

from homeassistant.components.notify import (
    ATTR_TITLE,
    PLATFORM_SCHEMA as NOTIFY_PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

CONF_ROOM_ID = "room_id"

PLATFORM_SCHEMA = NOTIFY_PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_TOKEN): cv.string, vol.Required(CONF_ROOM_ID): cv.string}
)


def get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> CiscoWebexNotificationService | None:
    """Get the Cisco Webex notification service."""
    client = WebexAPI(access_token=config[CONF_TOKEN])
    try:
        # Validate the token & room_id
        client.rooms.get(config[CONF_ROOM_ID])
    except exceptions.ApiError as error:
        _LOGGER.error(error)
        return None

    return CiscoWebexNotificationService(client, config[CONF_ROOM_ID])


class CiscoWebexNotificationService(BaseNotificationService):
    """The Cisco Webex Notification Service."""

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
                "Could not send Cisco Webex notification. Error: %s", api_error
            )
