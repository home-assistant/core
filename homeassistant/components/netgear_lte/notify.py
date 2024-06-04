"""Support for Netgear LTE notifications."""

from __future__ import annotations

import attr
import eternalegypt

from homeassistant.components.notify import ATTR_TARGET, BaseNotificationService
from homeassistant.const import CONF_RECIPIENT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_NOTIFY, DOMAIN, LOGGER


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> NetgearNotifyService | None:
    """Get the notification service."""
    if discovery_info is None:
        return None

    return NetgearNotifyService(hass, discovery_info)


@attr.s
class NetgearNotifyService(BaseNotificationService):
    """Implementation of a notification service."""

    hass = attr.ib()
    config = attr.ib()

    async def async_send_message(self, message="", **kwargs):
        """Send a message to a user."""

        modem_data = self.hass.data[DOMAIN].get_modem_data(self.config)
        if not modem_data:
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
                await modem_data.modem.sms(target, message)
            except eternalegypt.Error:
                LOGGER.error("Unable to send to %s", target)
