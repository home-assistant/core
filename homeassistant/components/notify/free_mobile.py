"""
Support for thr Free Mobile SMS platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.free_mobile/
"""
import logging

from homeassistant.components.notify import DOMAIN, BaseNotificationService
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_USERNAME
from homeassistant.helpers import validate_config

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ['freesms==0.1.0']


def get_service(hass, config):
    """Get the Free Mobile SMS notification service."""
    if not validate_config({DOMAIN: config},
                           {DOMAIN: [CONF_USERNAME,
                                     CONF_ACCESS_TOKEN]},
                           _LOGGER):
        return None

    return FreeSMSNotificationService(config[CONF_USERNAME],
                                      config[CONF_ACCESS_TOKEN])


# pylint: disable=too-few-public-methods
class FreeSMSNotificationService(BaseNotificationService):
    """Implement a notification service for the Free Mobile SMS service."""

    def __init__(self, username, access_token):
        """Initialize the service."""
        from freesms import FreeClient
        self.free_client = FreeClient(username, access_token)

    def send_message(self, message="", **kwargs):
        """Send a message to the Free Mobile user cell."""
        resp = self.free_client.send_sms(message)

        if resp.status_code == 400:
            _LOGGER.error("At least one parameter is missing")
        elif resp.status_code == 402:
            _LOGGER.error("Too much SMS send in a few time")
        elif resp.status_code == 403:
            _LOGGER.error("Wrong Username/Password")
        elif resp.status_code == 500:
            _LOGGER.error("Server error, try later")
