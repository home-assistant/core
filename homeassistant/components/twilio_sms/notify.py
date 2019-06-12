"""Twilio SMS platform for notify component."""
import logging

import voluptuous as vol

from homeassistant.components.twilio import DATA_TWILIO
import homeassistant.helpers.config_validation as cv

from homeassistant.components.notify import (ATTR_TARGET, PLATFORM_SCHEMA,
                                             BaseNotificationService)

_LOGGER = logging.getLogger(__name__)

CONF_FROM_NUMBER = "from_number"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_FROM_NUMBER):
        vol.All(cv.string,
                vol.Match(r"^\+?[1-9]\d{1,14}$|"
                          r"^(?=.{1,11}$)[a-zA-Z0-9\s]*"
                          r"[a-zA-Z][a-zA-Z0-9\s]*$")),
})


def get_service(hass, config, discovery_info=None):
    """Get the Twilio SMS notification service."""
    return TwilioSMSNotificationService(
        hass.data[DATA_TWILIO], config[CONF_FROM_NUMBER])


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

        for target in targets:
            self.client.messages.create(
                to=target, body=message, from_=self.from_number)
