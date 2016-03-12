"""
SendGrid notification service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.sendgrid/
"""
import logging

from homeassistant.components.notify import (
    ATTR_TITLE, DOMAIN, BaseNotificationService)
from homeassistant.helpers import validate_config

REQUIREMENTS = ['sendgrid>=1.6.0,<1.7.0']
_LOGGER = logging.getLogger(__name__)


def get_service(hass, config):
    """Get the SendGrid notification service."""
    if not validate_config({DOMAIN: config},
                           {DOMAIN: ['api_key', 'sender', 'recipient']},
                           _LOGGER):
        return None

    api_key = config['api_key']
    sender = config['sender']
    recipient = config['recipient']
    return SendgridNotificationService(api_key, sender, recipient)


# pylint: disable=too-few-public-methods
class SendgridNotificationService(BaseNotificationService):
    """Implement the notification service for email via Sendgrid."""

    def __init__(self, api_key, sender, recipient):
        """Initialize the service."""
        self.api_key = api_key
        self.sender = sender
        self.recipient = recipient

        from sendgrid import SendGridClient
        self._sg = SendGridClient(self.api_key)

    def send_message(self, message='', **kwargs):
        """Send an email to a user via SendGrid."""
        subject = kwargs.get(ATTR_TITLE)

        from sendgrid import Mail
        mail = Mail(from_email=self.sender, to=self.recipient,
                    html=message, text=message, subject=subject)
        self._sg.send(mail)
