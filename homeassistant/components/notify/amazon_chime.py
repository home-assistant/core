"""
Amazon Chime platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.amazon_chime/
"""


import logging

import voluptuous as vol

from homeassistant.components.notify import (
    BaseNotificationService, PLATFORM_SCHEMA)
from homeassistant.const import CONF_URL
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = []
_LOGGER = logging.getLogger(__name__)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_URL): cv.url
})


def get_service(hass, config, discovery_info=None):
    """Get the Amazon Chime service."""
    return AmazonChime(config[CONF_URL])


class AmazonChime(BaseNotificationService):
    """Implement the Amazon Chime Webhook service."""

    def __init__(self, webhook_url):
        """Initialize the service."""
        self.webhook_url = webhook_url

    def send_message(self, message='', **kwargs):
        """Send a message to a Chime webhook."""
        from requests import post, RequestException

        data = kwargs.get('data', {})

        if data.get('present_members', None):
            message += ' @Present'
        if data.get('all_members', None):
            message += ' @All'

        try:
            r = post(
                url=self.webhook_url,
                json={"Content": message}
            )
        except RequestException:
            _LOGGER.exception("Could not send Amazon Chime webhook service")
            return

        if r.status_code != 200:
            _LOGGER.exception("Invalid response: {}".format(r.text))
            return
        _LOGGER.info('Amazon Chime webhook successfully sent')
