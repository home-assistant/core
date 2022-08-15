"""Support for System Bridge notification service."""
from __future__ import annotations

import logging
from typing import Any

from systembridgeconnector.exceptions import (
    AuthenticationException,
    ConnectionClosedException,
    ConnectionErrorException,
)
from systembridgeconnector.models.notification import Notification
from systembridgeconnector.websocket_client import WebSocketClient

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TITLE_DEFAULT,
    BaseNotificationService,
)
from homeassistant.components.notify.const import ATTR_TARGET, ATTR_TITLE
from homeassistant.const import ATTR_ICON, CONF_API_KEY, CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

ATTR_IMAGE = "image"
ATTR_ACTIONS = "actions"


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> SystemBridgeNotificationService | None:
    """Get the System Bridge notification service."""
    return SystemBridgeNotificationService(hass)


class SystemBridgeNotificationService(BaseNotificationService):
    """Implement the notification service for System Bridge."""

    def __init__(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Initialize the service."""
        self._hass = hass

    @property
    def targets(self) -> dict[str, str]:
        """Return a dictionary of registered targets."""
        return {entry.entry_id: entry.title for entry in self.hass.data[DOMAIN].items()}

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

        for target in kwargs.get(ATTR_TARGET, []):
            _LOGGER.debug("Sending to target: %s", target)

            device_registry = dr.async_get(self.hass)
            device_entry = device_registry.async_get(target)
            if device_entry is None:
                _LOGGER.error("Device %s not found in device registry", target)
                continue
            entry = next(
                entry
                for entry in self.hass.config_entries.async_entries(DOMAIN)
                if entry.entry_id in device_entry.config_entries
            )
            if entry is None:
                _LOGGER.error("Device %s not found in config entries", target)
                continue
            _LOGGER.debug(
                "Sending notification to entry: %s - %s", entry.entry_id, entry.title
            )

            websocket_client = WebSocketClient(
                entry.data[CONF_HOST],
                entry.data[CONF_PORT],
                entry.data[CONF_API_KEY],
            )
            try:
                await websocket_client.connect(
                    session=async_get_clientsession(self.hass)
                )
                await websocket_client.send_notification(notification)
            except AuthenticationException as exception:
                raise HomeAssistantError(
                    f"Authentication error when connecting to {entry.data[CONF_HOST]}"
                ) from exception
            except (
                ConnectionClosedException,
                ConnectionErrorException,
            ) as exception:
                raise HomeAssistantError(
                    f"Connection error when connecting to {entry.data[CONF_HOST]}"
                ) from exception
