"""Support for Netgear LTE notifications."""

from __future__ import annotations

from typing import Any

import eternalegypt
from eternalegypt.eternalegypt import Modem

from homeassistant.components.notify import ATTR_TARGET, BaseNotificationService
from homeassistant.const import CONF_RECIPIENT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_NOTIFY, LOGGER


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> NetgearNotifyService | None:
    """Get the notification service."""
    if discovery_info is None:
        return None

    return NetgearNotifyService(config, discovery_info)


class NetgearNotifyService(BaseNotificationService):
    """Implementation of a notification service."""

    def __init__(
        self,
        config: ConfigType,
        discovery_info: dict[str, Any],
    ) -> None:
        """Initialize the service."""
        self.config = config
        self.modem: Modem = discovery_info["modem"]

    async def async_send_message(self, message="", **kwargs):
        """Send a message to a user."""

        if not self.modem.token:
            LOGGER.error("Modem not ready")
            return
        if not (targets := kwargs.get(ATTR_TARGET)):
            targets = self.config[CONF_NOTIFY][CONF_RECIPIENT]
        if not targets:
            LOGGER.warning("No recipients")
            return

        if not message:
            return

        for target in targets:
            try:
                await self.modem.sms(target, message)
            except eternalegypt.Error:
                LOGGER.error("Unable to send to %s", target)
