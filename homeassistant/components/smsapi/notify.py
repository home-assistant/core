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

    smsapi_client = SmsApiPlClient(access_token=config[CONF_ACCESS_TOKEN])

    try:
        smsapi_client.account.balance()
        return SMSApiNotificationService(
            smsapi_client, config[CONF_RECIPIENT])
    except SmsApiException as exc:
        _LOGGER.error(exc)
        return None


class SMSApiNotificationService(BaseNotificationService):
    """Implement a notification service for the SMSApi service."""

    def __init__(self, client, recipient):
        """Initialize the service."""

        self.client = client
        self._recipient = recipient

    def send_message(self, message="", **kwargs):
        """Send a SMS message via SMSApi."""

        try:
            self.client.sms.send(to=self._recipient, message=message)
        except SmsApiException as exc:
            _LOGGER.error(exc)
