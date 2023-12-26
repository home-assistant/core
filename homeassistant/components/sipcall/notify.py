"""Discord platform for notify component."""
from __future__ import annotations

import logging
from typing import Any

from nanosip import Invite, SIPAuthCreds, async_call_and_cancel

from homeassistant.components.notify import BaseNotificationService
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_SIP_DOMAIN, CONF_SIP_SERVER, DEFAULT_DURATION

_LOGGER = logging.getLogger(__name__)


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> SIPCallNotificationService | None:
    """Get the SIPCall notification service."""
    if discovery_info is None:
        return None

    return SIPCallNotificationService(discovery_info)


class SIPCallNotificationService(BaseNotificationService):
    """Implement the notification service for SIP Call."""

    def __init__(self, config: dict) -> None:
        """Initialize the service."""

        self.config = config

        self.auth_creds = SIPAuthCreds(
            username=config[CONF_USERNAME],
            password=config[CONF_PASSWORD],
        )

    async def async_send_message(self, message: str = "", **kwargs: Any) -> None:
        """Make a short call and hang up."""

        # A callee must be specified through the notification target
        try:
            callee = kwargs["target"]
        except (TypeError, KeyError):
            _LOGGER.error(
                "Notifications using sipcall require a 'target' (i.e. the callee) to be specified"
            )
            return

        if isinstance(callee, list):
            callee = callee[0]

        # A duration in seconds is optional under 'data'
        try:
            duration = kwargs["data"]["duration"]
        except (TypeError, KeyError):
            duration = DEFAULT_DURATION

        auth_creds = SIPAuthCreds(
            username=self.config[CONF_USERNAME], password=self.config[CONF_PASSWORD]
        )

        inv = Invite(
            uri_from=f"sip:{self.config[CONF_USERNAME]}@{self.config[CONF_SIP_DOMAIN]}",
            uri_to=f"sip:{callee}@{self.config[CONF_SIP_SERVER]}",
            uri_via=self.config[CONF_SIP_SERVER],
            auth_creds=auth_creds,
        )

        await async_call_and_cancel(inv, duration)
