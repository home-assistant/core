"""Support for LG WebOS TV notification service."""

from __future__ import annotations

import logging
from typing import Any

from aiowebostv import WebOsClient, WebOsTvPairError

from homeassistant.components.notify import ATTR_DATA, BaseNotificationService
from homeassistant.const import ATTR_ICON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import ATTR_CONFIG_ENTRY_ID, DATA_CONFIG_ENTRY, DOMAIN, WEBOSTV_EXCEPTIONS

_LOGGER = logging.getLogger(__name__)


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> BaseNotificationService | None:
    """Return the notify service."""

    if discovery_info is None:
        return None

    client = hass.data[DOMAIN][DATA_CONFIG_ENTRY][discovery_info[ATTR_CONFIG_ENTRY_ID]]

    return LgWebOSNotificationService(client)


class LgWebOSNotificationService(BaseNotificationService):
    """Implement the notification service for LG WebOS TV."""

    def __init__(self, client: WebOsClient) -> None:
        """Initialize the service."""
        self._client = client

    async def async_send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send a message to the tv."""
        try:
            if not self._client.is_connected():
                await self._client.connect()

            data = kwargs[ATTR_DATA]
            icon_path = data.get(ATTR_ICON) if data else None
            await self._client.send_message(message, icon_path=icon_path)
        except WebOsTvPairError:
            _LOGGER.error("Pairing with TV failed")
        except FileNotFoundError:
            _LOGGER.error("Icon %s not found", icon_path)
        except WEBOSTV_EXCEPTIONS:
            _LOGGER.error("TV unreachable")
