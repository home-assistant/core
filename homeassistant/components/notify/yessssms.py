"""
Support for the YesssSMS platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.yessssms/
"""
import logging

import voluptuous as vol

from homeassistant.components.notify import (
    PLATFORM_SCHEMA, BaseNotificationService)
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_RECIPIENT
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['YesssSMS==0.1.1b3']

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_RECIPIENT): cv.string,
})


def get_service(hass, config, discovery_info=None):
    """Get the YesssSMS notification service."""
    return YesssSMSNotificationService(
        config[CONF_USERNAME], config[CONF_PASSWORD], config[CONF_RECIPIENT])


class YesssSMSNotificationService(BaseNotificationService):
    """Implement a notification service for the YesssSMS service."""

    def __init__(self, username, password, recipient):
        """Initialize the service."""
        from YesssSMS import YesssSMS
        self.yesss = YesssSMS(username, password)
        self._recipient = recipient

    def send_message(self, message="", **kwargs):
        """Send a SMS message via Yesss.at's website."""
        try:
            self.yesss.send(self._recipient, message)
        except ValueError as ex:
            if str(ex).startswith("YesssSMS:"):
                _LOGGER.error(str(ex))
        except RuntimeError as ex:
            if str(ex).startswith("YesssSMS:"):
                _LOGGER.error(str(ex))
