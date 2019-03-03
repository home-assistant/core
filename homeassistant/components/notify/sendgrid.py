"""
SendGrid notification service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.sendgrid/
"""
import logging

import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_TITLE, ATTR_TITLE_DEFAULT, PLATFORM_SCHEMA, BaseNotificationService)
from homeassistant.const import (
    CONF_API_KEY, CONF_SENDER, CONF_RECIPIENT, CONTENT_TYPE_TEXT_PLAIN)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['sendgrid==5.6.0']

_LOGGER = logging.getLogger(__name__)

CONF_SENDER_NAME = 'sender_name'

# pylint: disable=no-value-for-parameter
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_SENDER): vol.Email(),
    vol.Required(CONF_RECIPIENT): vol.Email(),
    vol.Optional(CONF_SENDER_NAME, default='Home Assistant'): cv.string,
})


def get_service(hass, config, discovery_info=None):
    """Get the SendGrid notification service."""
    api_key = config.get(CONF_API_KEY)
    sender = config.get(CONF_SENDER)
    recipient = config.get(CONF_RECIPIENT)
    sender_name = config.get(CONF_SENDER_NAME)

    return SendgridNotificationService(api_key, sender, recipient, sender_name)


class SendgridNotificationService(BaseNotificationService):
    """Implementation the notification service for email via Sendgrid."""

    def __init__(self, api_key, sender, recipient, sender_name):
        """Initialize the service."""
        from sendgrid import SendGridAPIClient

        self.api_key = api_key
        self.sender = sender
        self.sender_name = sender_name
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
                "email": self.sender,
                "name": self.sender_name
            },
            "content": [
                {
                    "type": CONTENT_TYPE_TEXT_PLAIN,
                    "value": message
                }
            ]
        }

        response = self._sg.client.mail.send.post(request_body=data)
        if response.status_code != 202:
            _LOGGER.error("Unable to send notification")
