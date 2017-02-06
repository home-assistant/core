"""
Support for the Mailgun mail service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.mailgun/
"""
import logging

import voluptuous as vol

from homeassistant.components.notify import (
    PLATFORM_SCHEMA, BaseNotificationService,
    ATTR_TITLE, ATTR_TITLE_DEFAULT, ATTR_DATA)
from homeassistant.const import (CONF_TOKEN, CONF_DOMAIN,
                                 CONF_RECIPIENT, CONF_SENDER)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ['https://github.com/pschmitt/pymailgun/'
                'archive/1.2.zip#'
                'pymailgun==1.2']

# Images to attach to notification
ATTR_IMAGES = 'images'

# Default sender name
DEFAULT_SENDER = 'hass@{domain}'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_DOMAIN): cv.string,
    vol.Required(CONF_TOKEN): cv.string,
    vol.Optional(CONF_SENDER): vol.Email(),
    vol.Required(CONF_RECIPIENT): vol.Email(),
})


def get_service(hass, config, discovery_info=None):
    """Get the Mailgun notification service."""
    return MailgunNotificationService(config.get(CONF_DOMAIN),
                                      config.get(CONF_TOKEN),
                                      config.get(CONF_SENDER),
                                      config.get(CONF_RECIPIENT))


class MailgunNotificationService(BaseNotificationService):
    """Implement a notification service for the Mailgun mail service."""

    def __init__(self, domain, token, sender, recipient):
        """Initialize the service."""
        from pymailgun import Client
        self._sender = sender if sender is not None \
                              else DEFAULT_SENDER.format(domain=domain)
        self._recipient = recipient
        self._client = Client(token, domain)

    def send_message(self, message="", **kwargs):
        """Send a mail to the recipient."""
        subject = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)
        data = kwargs.get(ATTR_DATA)
        files = data.get(ATTR_IMAGES) if data else None

        resp = self._client.send_mail(sender=self._sender, to=self._recipient,
                                      subject=subject, text=message,
                                      files=files)
        if not resp.ok:
            _LOGGER.error('Failed to send message: '
                          '[{}] {}'.format(resp.status_code, resp.json()))
        else:
            _LOGGER.debug('Message sent: {}'.format(resp.json()))
