"""SendGrid notification service."""
import logging

import voluptuous as vol

from homeassistant.const import (
    CONF_API_KEY, CONF_RECIPIENT, CONF_SENDER, CONTENT_TYPE_TEXT_PLAIN)
import homeassistant.helpers.config_validation as cv

from homeassistant.components.notify import (
    ATTR_TITLE, ATTR_TITLE_DEFAULT, PLATFORM_SCHEMA, BaseNotificationService)

_LOGGER = logging.getLogger(__name__)

CONF_SENDER_NAME = 'sender_name'

DEFAULT_SENDER_NAME = 'Home Assistant'

# pylint: disable=no-value-for-parameter
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_SENDER): vol.Email(),
    vol.Required(CONF_RECIPIENT): vol.Email(),
    vol.Optional(CONF_SENDER_NAME, default=DEFAULT_SENDER_NAME): cv.string,
})


def get_service(hass, config, discovery_info=None):
    """Get the SendGrid notification service."""
    return SendgridNotificationService(config)


class SendgridNotificationService(BaseNotificationService):
    """Implementation the notification service for email via Sendgrid."""

    def __init__(self, config):
        """Initialize the service."""
        from sendgrid import SendGridAPIClient

        self.api_key = config[CONF_API_KEY]
        self.sender = config[CONF_SENDER]
        self.sender_name = config[CONF_SENDER_NAME]
        self.recipient = config[CONF_RECIPIENT]

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
