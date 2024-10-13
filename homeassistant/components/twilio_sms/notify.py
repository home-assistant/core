"""Twilio SMS platform for notify component."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TARGET,
    PLATFORM_SCHEMA as NOTIFY_PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.components.twilio import DATA_TWILIO
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

CONF_FROM_NUMBER = "from_number"
ATTR_MEDIAURL = "media_url"

PLATFORM_SCHEMA = NOTIFY_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_FROM_NUMBER): vol.All(
            cv.string,
            vol.Match(
                r"^\+?[1-9]\d{1,14}$|"
                r"^(?=.{1,11}$)[a-zA-Z0-9\s]*"
                r"[a-zA-Z][a-zA-Z0-9\s]*$"
                r"^(?:[a-zA-Z]+)\:?\+?[1-9]\d{1,14}$|"
            ),
        )
    }
)


def get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> TwilioSMSNotificationService | None:
    """Get the Twilio SMS notification service."""
    return TwilioSMSNotificationService(
        hass.data[DATA_TWILIO], config[CONF_FROM_NUMBER]
    )


class TwilioSMSNotificationService(BaseNotificationService):
    """Implement the notification service for the Twilio SMS service."""

    def __init__(self, twilio_client, from_number):
        """Initialize the service."""
        self.client = twilio_client
        self.from_number = from_number

    def send_message(self, message="", **kwargs):
        """Send SMS to specified target user cell."""
        targets = kwargs.get(ATTR_TARGET)
        data = kwargs.get(ATTR_DATA) or {}
        twilio_args = {"body": message, "from_": self.from_number}

        if ATTR_MEDIAURL in data:
            twilio_args[ATTR_MEDIAURL] = data[ATTR_MEDIAURL]

        if not targets:
            _LOGGER.warning("At least 1 target is required")
            return

        for target in targets:
            self.client.messages.create(to=target, **twilio_args)
