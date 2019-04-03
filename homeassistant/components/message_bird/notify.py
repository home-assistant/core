"""
MessageBird platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.message_bird/
"""
import logging

import voluptuous as vol

from homeassistant.const import CONF_API_KEY, CONF_SENDER
import homeassistant.helpers.config_validation as cv

from homeassistant.components.notify import (ATTR_TARGET, PLATFORM_SCHEMA,
                                             BaseNotificationService)

REQUIREMENTS = ['messagebird==1.2.0']

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Optional(CONF_SENDER, default='HA'):
        vol.All(cv.string, vol.Match(r"^(\+?[1-9]\d{1,14}|\w{1,11})$")),
})


def get_service(hass, config, discovery_info=None):
    """Get the MessageBird notification service."""
    import messagebird

    client = messagebird.Client(config[CONF_API_KEY])
    try:
        # validates the api key
        client.balance()
    except messagebird.client.ErrorException:
        _LOGGER.error("The specified MessageBird API key is invalid")
        return None

    return MessageBirdNotificationService(config.get(CONF_SENDER), client)


class MessageBirdNotificationService(BaseNotificationService):
    """Implement the notification service for MessageBird."""

    def __init__(self, sender, client):
        """Initialize the service."""
        self.sender = sender
        self.client = client

    def send_message(self, message=None, **kwargs):
        """Send a message to a specified target."""
        from messagebird.client import ErrorException

        targets = kwargs.get(ATTR_TARGET)
        if not targets:
            _LOGGER.error("No target specified")
            return

        for target in targets:
            try:
                self.client.message_create(
                    self.sender, target, message, {'reference': 'HA'})
            except ErrorException as exception:
                _LOGGER.error("Failed to notify %s: %s", target, exception)
                continue
