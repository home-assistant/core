"""Support for SMS notification services."""
import logging

import voluptuous as vol

from homeassistant.components.notify import PLATFORM_SCHEMA, BaseNotificationService
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv

from . import CONF_PHONE_NUMBER, STATE_MACHINE

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_PHONE_NUMBER): cv.string, vol.Optional(CONF_NAME): cv.string}
)


def get_service(hass, config, discovery_info=None):
    """Get the SMS notification service."""
    number = config[CONF_PHONE_NUMBER]
    return SMSNotificationService(number)


class SMSNotificationService(BaseNotificationService):
    """Implement the notification service for SMS."""

    def __init__(self, number):
        """Initialize the service."""
        self.number = number

    def send_message(self, message="", **kwargs):
        """Send SMS message."""
        # Prepare message data
        # We tell that we want to use first SMSC number stored in phone
        gammu_message = {
            "Text": message,
            "SMSC": {"Location": 1},
            "Number": self.number,
        }
        STATE_MACHINE.SendSMS(gammu_message)
