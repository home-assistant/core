"""Support for System Bridge notification service."""
from __future__ import annotations

import logging
from typing import Any

from systembridgeconnector.models.notification import Notification

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TITLE_DEFAULT,
    BaseNotificationService,
)
from homeassistant.components.notify.const import ATTR_TITLE
from homeassistant.const import ATTR_ICON, CONF_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN
from .coordinator import SystemBridgeDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

ATTR_IMAGE = "image"
ATTR_ACTIONS = "actions"


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> SystemBridgeNotificationService | None:
    """Get the System Bridge notification service."""
    if discovery_info is None:
        return None

    coordinator: SystemBridgeDataUpdateCoordinator = hass.data[DOMAIN][
        discovery_info[CONF_ENTITY_ID]
    ]

    return SystemBridgeNotificationService(coordinator)


class SystemBridgeNotificationService(BaseNotificationService):
    """Implement the notification service for System Bridge."""

    def __init__(
        self,
        coordinator: SystemBridgeDataUpdateCoordinator,
    ) -> None:
        """Initialize the service."""
        self._coordinator: SystemBridgeDataUpdateCoordinator = coordinator

    async def async_send_message(
        self,
        message: str = "",
        **kwargs: Any,
    ) -> None:
        """Send a message."""
        data = kwargs.get(ATTR_DATA)

        notification = Notification(
            title=kwargs.get(
                ATTR_TITLE,
                data.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)
                if data is not None
                else ATTR_TITLE_DEFAULT,
            ),
            message=message,
            icon=data.get(ATTR_ICON) if data is not None else None,
            image=data.get(ATTR_IMAGE) if data is not None else None,
            actions=data.get(ATTR_ACTIONS) if data is not None else None,
            timeout=data.get("timeout") if data is not None else None,
        )

        _LOGGER.debug("Sending notification: %s", notification.json())

        await self._coordinator.websocket_client.send_notification(notification)
