"""Support for SIP Call notification."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.notify import PLATFORM_SCHEMA, BaseNotificationService
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .utils import Invite, SIPAuthCreds, call_and_cancel

CONF_URI_FROM = "uri_from"
CONF_URI_VIA = "uri_via"
CONF_URI_TO = "uri_to"
CONF_DURATION = "duration"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_URI_FROM): cv.string,
        vol.Required(CONF_URI_VIA): cv.string,
        vol.Required(CONF_URI_TO): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_DURATION, default=2): cv.positive_int,
    }
)


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> SIPCallNotificationService:
    """Get the SIPCall notification service."""
    return SIPCallNotificationService(config)


class SIPCallNotificationService(BaseNotificationService):
    """Implement the notification service for the File service."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the service."""
        self.uri_from: str = config[CONF_URI_FROM]
        self.uri_via: str = config[CONF_URI_VIA]
        self.uri_to: str = config[CONF_URI_TO]
        self.duration: int = config[CONF_DURATION]

        self.auth_creds = SIPAuthCreds(
            username=config[CONF_USERNAME],
            password=config[CONF_PASSWORD],
        )

    async def async_send_message(self, message: str = "", **kwargs: Any) -> None:
        """Make a short call."""

        logging.warning("SIPCall: To %s", self.uri_to)

        inv = Invite(
            uri_from=self.uri_from,
            uri_to=self.uri_to,
            uri_via=self.uri_via,
            auth_creds=self.auth_creds,
        )

        await call_and_cancel(inv, self.duration)
