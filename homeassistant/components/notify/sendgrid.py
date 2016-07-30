"""
SendGrid notification service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.sendgrid/
"""
import logging

from homeassistant.components.notify import (
    ATTR_TITLE, DOMAIN, BaseNotificationService)
from homeassistant.helpers import validate_config

REQUIREMENTS = ['sendgrid==3.0.7']
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
    """Implementation the notification service for email via Sendgrid."""

    def __init__(self, api_key, sender, recipient):
        """Initialize the service."""
        from sendgrid import SendGridAPIClient

        self.api_key = api_key
        self.sender = sender
        self.recipient = recipient

        self._sg = SendGridAPIClient(apikey=self.api_key)

    def send_message(self, message='', **kwargs):
        """Send an email to a user via SendGrid."""
        subject = kwargs.get(ATTR_TITLE)

        data = {
            "personalizations": [
                {
                    "to": [
                        {
                            "email": self.recipient
                        }
                    ],
                    "subject": subject
                }
            ],
            "from": {
                "email": self.sender
            },
            "content": [
                {
                    "type": "text/plain",
                    "value": message
                }
            ]
        }

        response = self._sg.client.mail.send.post(request_body=data)
        if response.status_code is not 202:
            _LOGGER.error('Unable to send notification with SendGrid')
