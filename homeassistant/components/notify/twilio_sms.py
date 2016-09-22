"""
Twilio SMS platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.twilio_sms/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.notify import (
    ATTR_TARGET, PLATFORM_SCHEMA, BaseNotificationService)

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ["twilio==5.4.0"]


CONF_ACCOUNT_SID = "account_sid"
CONF_AUTH_TOKEN = "auth_token"
CONF_FROM_NUMBER = "from_number"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ACCOUNT_SID): cv.string,
    vol.Required(CONF_AUTH_TOKEN): cv.string,
    vol.Required(CONF_FROM_NUMBER):
        vol.All(cv.string, vol.Match(r"^\+?[1-9]\d{1,14}$")),
})


def get_service(hass, config):
    """Get the Twilio SMS notification service."""
    # pylint: disable=import-error
    from twilio.rest import TwilioRestClient

    twilio_client = TwilioRestClient(config[CONF_ACCOUNT_SID],
                                     config[CONF_AUTH_TOKEN])

    return TwilioSMSNotificationService(twilio_client,
                                        config[CONF_FROM_NUMBER])


# pylint: disable=too-few-public-methods
class TwilioSMSNotificationService(BaseNotificationService):
    """Implement the notification service for the Twilio SMS service."""

    def __init__(self, twilio_client, from_number):
        """Initialize the service."""
        self.client = twilio_client
        self.from_number = from_number

    def send_message(self, message="", **kwargs):
        """Send SMS to specified target user cell."""
        targets = kwargs.get(ATTR_TARGET)

        if not targets:
            _LOGGER.info("At least 1 target is required")
            return

        if not isinstance(targets, list):
            targets = [targets]

        for target in targets:
            self.client.messages.create(to=target, body=message,
                                        from_=self.from_number)
