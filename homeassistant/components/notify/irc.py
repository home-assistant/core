"""
IRC platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.irc/
"""
import logging

import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_TARGET, PLATFORM_SCHEMA, BaseNotificationService)
from homeassistant.components.irc import CONF_NETWORK, DATA_IRC
import homeassistant.helpers.config_validation as cv

DEPENDENCIES = ['irc']

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NETWORK): cv.string,
})


# pylint: disable=unused-variable
def get_service(hass, config, discovery_info=None):
    """Get the IRC notification service."""
    if discovery_info is None:
        return

    network = discovery_info.get(CONF_NETWORK)
    if network not in hass.data[DATA_IRC]:
        _LOGGER.error('Unknown IRC network: %s', network)
        return None

    plugin = hass.data[DATA_IRC][network]
    return IRCNotificationService(plugin)


class IRCNotificationService(BaseNotificationService):
    """Implement the notification service for IRC."""

    def __init__(self, plugin):
        """Initialize the service."""
        self.plugin = plugin

    def send_message(self, message="", **kwargs):
        """Send a message to a user."""
        if kwargs.get(ATTR_TARGET) is None:
            _LOGGER.error('No target specified')
            return

        for target in kwargs.get(ATTR_TARGET):
            self.plugin.context.privmsg(target, message)
