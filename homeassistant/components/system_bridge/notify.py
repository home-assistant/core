"""Support for System Bridge notification service."""

import logging
from typing import Any, override

from systembridgeconnector.const import EventType
from systembridgeconnector.exceptions import ConnectionClosedException
from systembridgeconnector.models.notification import Notification
from systembridgeconnector.models.response import Response

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    BaseNotificationService,
    NotifyEntity,
    NotifyEntityFeature,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ENTITY_ID, CONF_HOST, CONF_PORT
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
ATTR_ICON = "icon"
ATTR_IMAGE = "image"
ATTR_TIMEOUT = "timeout"

PARALLEL_UPDATES = 0


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


async def _async_send_notification(
    coordinator: SystemBridgeDataUpdateCoordinator, notification: Notification
) -> Response:
    """Send a notification, raising if it isn't sent."""
    try:
        response = await coordinator.websocket_client.send_notification(notification)
    except (ConnectionClosedException, ConnectionResetError) as e:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="send_message_failed",
            translation_placeholders={
                "title": coordinator.config_entry.title,
                "host": coordinator.config_entry.data[CONF_HOST],
            },
        ) from e
    if response.type == EventType.ERROR:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="notification_failed",
            translation_placeholders={"error": response.message or ""},
        )
    return response


class SystemBridgeNotifyEntity(SystemBridgeEntity, NotifyEntity):
    """Representation of a notification entity."""

    _attr_supported_features = NotifyEntityFeature.TITLE
    _attr_name = None

    @override
    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send a message via notify.send_message action."""
        await _async_send_notification(
            self.coordinator,
            Notification(
                message=message, title=ATTR_TITLE_DEFAULT if title is None else title
            ),
        )


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> SystemBridgeNotificationService | None:
    """Get the System Bridge notification service."""
    if discovery_info is None:
        return None

    return SystemBridgeNotificationService(discovery_info[CONF_ENTITY_ID])


class SystemBridgeNotificationService(BaseNotificationService):
    """Implement the notification service for System Bridge."""

    def __init__(self, entry_id: str) -> None:
        """Initialize the service."""
        self._entry_id = entry_id

    @override
    async def async_send_message(
        self,
        message: str = "",
        **kwargs: Any,
    ) -> None:
        """Send a message."""
        # The service outlives reloads, so use the entry's current connection
        entry: SystemBridgeConfigEntry | None = (
            self.hass.config_entries.async_get_entry(self._entry_id)
        )
        if entry is None or entry.state is not ConfigEntryState.LOADED:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="entry_not_loaded",
                translation_placeholders={"entry_id": self._entry_id},
            )

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

        await _async_send_notification(entry.runtime_data, notification)
