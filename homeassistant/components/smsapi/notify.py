"""Support for the SMSApi platform."""
import logging

from smsapi.client import SmsApiPlClient
from smsapi.exception import SmsApiException
import voluptuous as vol

from homeassistant.components.notify import (
    PLATFORM_SCHEMA, BaseNotificationService)
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_RECIPIENT
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ACCESS_TOKEN): cv.string,
    vol.Required(CONF_RECIPIENT): cv.string,
})


def get_service(hass, config, discovery_info=None):
    """Get the SMSApi notification service."""
    return SMSApiNotificationService(
        config[CONF_ACCESS_TOKEN], config[CONF_RECIPIENT])


class SMSApiNotificationService(BaseNotificationService):
    """Implement a notification service for the SMSApi service."""

    def __init__(self, access_token, recipient):
        """Initialize the service."""

        self.smsapi = SmsApiPlClient(access_token=access_token)
        self._recipient = recipient

    def send_message(self, message="", **kwargs):
        """Send a SMS message via SMSApi."""

        try:
            self.smsapi.sms.send(to=self._recipient, message=message)
        except SmsApiException as exc:
            _LOGGER.error(exc)
