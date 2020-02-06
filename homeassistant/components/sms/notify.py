"""Support for SMS notification services."""
import logging

import gammu  # pylint: disable=import-error, no-member
import voluptuous as vol

from homeassistant.components.notify import PLATFORM_SCHEMA, BaseNotificationService
from homeassistant.const import CONF_NAME, CONF_RECIPIENT
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_RECIPIENT): cv.string, vol.Optional(CONF_NAME): cv.string}
)


def get_service(hass, config, discovery_info=None):
    """Get the SMS notification service."""
    gateway = hass.data[DOMAIN]
    number = config[CONF_RECIPIENT]
    return SMSNotificationService(gateway, number)


class SMSNotificationService(BaseNotificationService):
    """Implement the notification service for SMS."""

    def __init__(self, gateway, number):
        """Initialize the service."""
        self.gateway = gateway
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
        try:
            self.gateway.SendSMS(gammu_message)
        except gammu.GSMError as exc:  # pylint: disable=no-member
            _LOGGER.error("Sending to %s failed: %s", self.number, exc)
