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

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize the service."""

        self.config = config

        self.auth_creds = SIPAuthCreds(
            username=config[CONF_USERNAME],
            password=config[CONF_PASSWORD],
        )

    @staticmethod
    async def make_call(config: dict[str, Any], callee: str, duration: int):
        """Make a SIP call to the given callee hanging up after duration seconds."""

        auth_creds = SIPAuthCreds(
            username=config[CONF_USERNAME], password=config[CONF_PASSWORD]
        )

        inv = Invite(
            uri_from=f"sip:{config[CONF_USERNAME]}@{config[CONF_SIP_DOMAIN]}",
            uri_to=f"sip:{callee}@{config[CONF_SIP_DOMAIN]}",
            uri_via=config[CONF_SIP_SERVER],
            auth_creds=auth_creds,
        )

        return await async_call_and_cancel(
            inv, duration, sip_server=config[CONF_SIP_SERVER]
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

        await self.make_call(self.config, callee, duration)
