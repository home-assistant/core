"""Support for Free Mobile SMS platform."""
import logging

from freesms import FreeClient
import voluptuous as vol

from homeassistant.components.notify import PLATFORM_SCHEMA, BaseNotificationService
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_USERNAME,
    HTTP_BAD_REQUEST,
    HTTP_FORBIDDEN,
    HTTP_INTERNAL_SERVER_ERROR,
)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_USERNAME): cv.string, vol.Required(CONF_ACCESS_TOKEN): cv.string}
)


def get_service(hass, config, discovery_info=None):
    """Get the Free Mobile SMS notification service."""
    return FreeSMSNotificationService(config[CONF_USERNAME], config[CONF_ACCESS_TOKEN])


class FreeSMSNotificationService(BaseNotificationService):
    """Implement a notification service for the Free Mobile SMS service."""

    def __init__(self, username, access_token):
        """Initialize the service."""
        self.free_client = FreeClient(username, access_token)

    def send_message(self, message="", **kwargs):
        """Send a message to the Free Mobile user cell."""
        resp = self.free_client.send_sms(message)

        if resp.status_code == HTTP_BAD_REQUEST:
            _LOGGER.error("At least one parameter is missing")
        elif resp.status_code == 402:
            _LOGGER.error("Too much SMS send in a few time")
        elif resp.status_code == HTTP_FORBIDDEN:
            _LOGGER.error("Wrong Username/Password")
        elif resp.status_code == HTTP_INTERNAL_SERVER_ERROR:
            _LOGGER.error("Server error, try later")
