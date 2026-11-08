"""Support for System Bridge notification service."""

from datetime import timedelta
import logging
from typing import Any, override

from systembridgeconnector.const import EventType
from systembridgeconnector.exceptions import ConnectionClosedException
from systembridgeconnector.models.notification import Notification, NotificationButton
from systembridgeconnector.models.response import Response

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    BaseNotificationService,
    NotifyEntity,
    NotifyEntityFeature,
)
from homeassistant.const import CONF_ENTITY_ID, CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, ServiceResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN
from .coordinator import SystemBridgeConfigEntry, SystemBridgeDataUpdateCoordinator
from .entity import SystemBridgeEntity
from .issue import async_deprecated_notify_action_call

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

    async def system_bridge_send_message(
        self,
        message: str,
        title: str = ATTR_TITLE_DEFAULT,
        icon: str | None = None,
        urgency: str | None = None,
        duration: timedelta | None = None,
        buttons: list[dict[str, str]] | None = None,
        sound: str | None = None,
        url: str | None = None,
        path: str | None = None,
    ) -> ServiceResponse:
        """Send a message via the system_bridge.send_message action."""
        response = await _async_send_notification(
            self.coordinator,
            Notification(
                title=title,
                message=message,
                icon=icon,
                urgency=urgency,
                duration=(
                    None if duration is None else int(duration.total_seconds() * 1000)
                ),
                buttons=(
                    None
                    if buttons is None
                    else [NotificationButton(**button) for button in buttons]
                ),
                sound=sound,
                action_url=url,
                action_path=path,
            ),
        )
        self._async_record_notification()
        # Versions before 5.20.0 don't reply with the id
        data = response.data if isinstance(response.data, dict) else {}
        return {"id": data.get("id")}


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

    notification_service = SystemBridgeNotificationService(entry.runtime_data)
    # The notify platform skips an action that already exists, so remove it
    # with the entry and let the next setup register its own
    entry.async_on_unload(notification_service.async_unregister_services)
    return notification_service


class SystemBridgeNotificationService(BaseNotificationService):
    """Implement the notification service for System Bridge."""

    def __init__(self, coordinator: SystemBridgeDataUpdateCoordinator) -> None:
        """Initialize the service."""
        self._coordinator = coordinator

    @override
    async def async_send_message(
        self,
        message: str = "",
        **kwargs: Any,
    ) -> None:
        """Send a message."""
        async_deprecated_notify_action_call(self.hass, self._service_name)

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

        await _async_send_notification(self._coordinator, notification)
