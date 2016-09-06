"""
SendGrid notification service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.sendgrid/
"""
import logging

import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_TITLE, ATTR_TITLE_DEFAULT, PLATFORM_SCHEMA, BaseNotificationService)
from homeassistant.const import (CONF_API_KEY, CONF_SENDER, CONF_RECIPIENT)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['sendgrid==3.4.0']

_LOGGER = logging.getLogger(__name__)

# pylint: disable=no-value-for-parameter
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_SENDER): vol.Email(),
    vol.Required(CONF_RECIPIENT): vol.Email(),
})


def get_service(hass, config):
    """Get the SendGrid notification service."""
    api_key = config.get(CONF_API_KEY)
    sender = config.get(CONF_SENDER)
    recipient = config.get(CONF_RECIPIENT)

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
        subject = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)

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
