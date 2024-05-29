"""Support for TP-Link LTE notifications."""

from __future__ import annotations

import logging
from typing import Any

import attr
import tp_connected

from homeassistant.components.notify import ATTR_TARGET, BaseNotificationService
from homeassistant.const import CONF_RECIPIENT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DATA_KEY, LTEData

_LOGGER = logging.getLogger(__name__)


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> TplinkNotifyService | None:
    """Get the notification service."""
    if discovery_info is None:
        return None
    return TplinkNotifyService(hass, discovery_info)


@attr.s
class TplinkNotifyService(BaseNotificationService):
    """Implementation of a notification service."""

    hass: HomeAssistant = attr.ib()
    config: dict[str, Any] = attr.ib()

    async def async_send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send a message to a user."""

        lte_data: LTEData = self.hass.data[DATA_KEY]
        modem_data = lte_data.get_modem_data(self.config)
        if not modem_data:
            _LOGGER.error("No modem available")
            return

        phone = self.config[CONF_RECIPIENT]
        targets = kwargs.get(ATTR_TARGET, phone)
        if targets and message:
            for target in targets:
                try:
                    await modem_data.modem.sms(target, message)
                except tp_connected.Error:
                    _LOGGER.error("Unable to send to %s", target)
