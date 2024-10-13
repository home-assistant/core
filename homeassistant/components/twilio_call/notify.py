"""Twilio Call platform for notify component."""

from __future__ import annotations

import logging
import urllib

from twilio.base.exceptions import TwilioRestException
import voluptuous as vol

from homeassistant.components.notify import (
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

PLATFORM_SCHEMA = NOTIFY_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_FROM_NUMBER): vol.All(
            cv.string, vol.Match(r"^\+?[1-9]\d{1,14}$")
        )
    }
)


def get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> TwilioCallNotificationService:
    """Get the Twilio Call notification service."""
    return TwilioCallNotificationService(
        hass.data[DATA_TWILIO], config[CONF_FROM_NUMBER]
    )


class TwilioCallNotificationService(BaseNotificationService):
    """Implement the notification service for the Twilio Call service."""

    def __init__(self, twilio_client, from_number):
        """Initialize the service."""
        self.client = twilio_client
        self.from_number = from_number

    def send_message(self, message="", **kwargs):
        """Call to specified target users."""
        if not (targets := kwargs.get(ATTR_TARGET)):
            _LOGGER.warning("At least 1 target is required")
            return

        if message.startswith(("http://", "https://")):
            twimlet_url = message
        else:
            twimlet_url = "http://twimlets.com/message?Message="
            twimlet_url += urllib.parse.quote(message, safe="")

        for target in targets:
            try:
                self.client.calls.create(
                    to=target, url=twimlet_url, from_=self.from_number
                )
            except TwilioRestException as exc:
                _LOGGER.error(exc)
