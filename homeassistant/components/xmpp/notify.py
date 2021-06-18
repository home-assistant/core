"""Support for XMPP notifications."""
import logging

import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_MESSAGE,
    ATTR_TARGET,
    PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.const import CONF_RECIPIENT, CONF_ROOM
import homeassistant.helpers.config_validation as cv

from .const import BOOL_GROUPCHAT, DOMAIN, SERVICE_SEND_MESSAGE

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_RECIPIENT): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_ROOM): vol.All(cv.ensure_list, [cv.string]),
    },
)


def get_service(hass, config, discovery_info=None):
    """Get the XMPP notification service."""
    return XMPPNotificationService(config.get(CONF_RECIPIENT), config.get(CONF_ROOM))


class XMPPNotificationService(BaseNotificationService):
    """Send notifications to a XMPP room."""

    def __init__(self, recipient, room):
        """Set up the XMPP notification service."""
        self._recipient = recipient
        self._room = room

    def send_message(self, message="", **kwargs):
        """Send the message to the XMPP server."""
        all_targets = kwargs.get(ATTR_TARGET) or [self._recipient] + [self._room]
        for target_list in all_targets:
            print(target_list, type(target_list))
            target_is_groupchat = False
            if target_list is None:
                continue
            if target_list is self._room:
                target_is_groupchat = True
            service_data = {
                ATTR_TARGET: target_list,
                BOOL_GROUPCHAT: target_is_groupchat,
            }
            data = kwargs.get(ATTR_DATA)
            if message is not None or message != "":
                service_data[ATTR_MESSAGE] = message
            if data is not None:
                service_data[ATTR_DATA] = data
            self.hass.services.call(
                DOMAIN, SERVICE_SEND_MESSAGE, service_data=service_data
            )
        return True
