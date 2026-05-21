"""Support for System Bridge notification service."""

import logging
from typing import Any

from systembridgeconnector.exceptions import ConnectionClosedException
from systembridgeconnector.models.notification import Notification

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    BaseNotificationService,
    NotifyEntity,
    NotifyEntityFeature,
)
from homeassistant.const import ATTR_ICON, CONF_ENTITY_ID, CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN
from .coordinator import SystemBridgeConfigEntry, SystemBridgeDataUpdateCoordinator
from .entity import SystemBridgeEntity

_LOGGER = logging.getLogger(__name__)

ATTR_ACTIONS = "actions"
ATTR_AUDIO = "audio"
ATTR_IMAGE = "image"
ATTR_TIMEOUT = "timeout"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SystemBridgeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the notification entity platform."""

    coordinator = config_entry.runtime_data

    async_add_entities(
        [SystemBridgeNotifyEntity(coordinator, config_entry.data[CONF_PORT])]
    )


class SystemBridgeNotifyEntity(SystemBridgeEntity, NotifyEntity):
    """Representation of a notification entity."""

    _attr_supported_features = NotifyEntityFeature.TITLE
    _attr_name = None

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send a message via notify.send_message action."""
        notification = Notification(
            message=message, title=ATTR_TITLE_DEFAULT if title is None else title
        )
        try:
            await self.coordinator.websocket_client.send_notification(notification)
        except ConnectionClosedException as e:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="send_message_failed",
                translation_placeholders={
                    "title": self.coordinator.config_entry.title,
                    "host": self.coordinator.config_entry.data[CONF_HOST],
                },
            ) from e


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> SystemBridgeNotificationService | None:
    """Get the System Bridge notification service."""
    if discovery_info is None:
        return None

    entry: SystemBridgeConfigEntry | None = hass.config_entries.async_get_entry(
        discovery_info[CONF_ENTITY_ID]
    )
    if entry is None:
        return None

    return SystemBridgeNotificationService(entry.runtime_data)


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
        data = kwargs.get(ATTR_DATA, {}) or {}

        notification = Notification(
            actions=data.get(ATTR_ACTIONS),
            audio=data.get(ATTR_AUDIO),
            icon=data.get(ATTR_ICON),
            image=data.get(ATTR_IMAGE),
            message=message,
            timeout=data.get(ATTR_TIMEOUT),
            title=kwargs.get(ATTR_TITLE, data.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)),
        )

        _LOGGER.debug("Sending notification: %s", notification)

        await self._coordinator.websocket_client.send_notification(notification)
