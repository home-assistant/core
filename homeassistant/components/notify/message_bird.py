"""
MessageBird platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.message_bird/
"""
import logging

from homeassistant.components.notify import (
    ATTR_TARGET, BaseNotificationService)
from homeassistant.const import CONF_API_KEY

CONF_SENDER = 'sender'

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ['messagebird==1.1.1']


def is_valid_sender(sender):
    """Test if the sender config option is valid."""
    length = len(sender)
    if length > 1:
        if sender[0] == '+':
            return sender[1:].isdigit()
        elif length <= 11:
            return sender.isalpha()
    return False


# pylint: disable=unused-argument
def get_service(hass, config):
    """Get the MessageBird notification service."""
    from messagebird import Client

    if CONF_API_KEY not in config:
        _LOGGER.error("Unable to find config key '%s'", CONF_API_KEY)
        return None

    sender = config.get(CONF_SENDER, 'HA')
    if not is_valid_sender(sender):
        _LOGGER.error('Sender is invalid: It must be a phone number or ' +
                      'a string not longer than 11 characters.')
        return None

    return MessageBirdNotificationService(sender, Client(config[CONF_API_KEY]))


# pylint: disable=too-few-public-methods
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
            _LOGGER.error('No target specified.')
            return

        if not isinstance(targets, list):
            targets = [targets]

        for target in targets:
            try:
                self.client.message_create(self.sender,
                                           target,
                                           message,
                                           {'reference': 'HA'})
            except ErrorException as exception:
                _LOGGER.error('Failed to notify %s: %s', target, exception)
                continue
