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
    DOMAIN as NOTIFY_DOMAIN,
    BaseNotificationService,
    NotifyEntity,
    NotifyEntityFeature,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ENTITY_ID, CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, ServiceResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util.hass_dict import HassKey

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

# Entries with the same hostname share a legacy action, by action name
_LEGACY_SERVICES: HassKey[dict[str, list[SystemBridgeNotificationService]]] = HassKey(
    f"{DOMAIN}_legacy_notify_services"
)


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
    # Discovery can run after the entry has started to unload
    if entry is None or entry.state not in (
        ConfigEntryState.SETUP_IN_PROGRESS,
        ConfigEntryState.LOADED,
    ):
        return None

    notification_service = SystemBridgeNotificationService(entry.runtime_data)
    entry.async_on_unload(notification_service.async_entry_unloaded)
    return notification_service


class SystemBridgeNotificationService(BaseNotificationService):
    """Implement the notification service for System Bridge."""

    def __init__(self, coordinator: SystemBridgeDataUpdateCoordinator) -> None:
        """Initialize the service."""
        self._coordinator = coordinator
        self._owns_action = False
        self._unloaded = False
        # The loaded services that share this service's action name
        self._registry: list[SystemBridgeNotificationService] | None = None

    async def async_entry_unloaded(self) -> None:
        """Remove the action with the entry, handing it to an entry that shares it."""
        self._unloaded = True
        if self._registry is None:
            return
        self._registry.remove(self)
        if not self._owns_action:
            return
        await self.async_unregister_services()
        if self._registry:
            await self._registry[0].async_register_services()

    @override
    async def async_register_services(self) -> None:
        """Register the action, unless the entry has unloaded or another has it."""
        # The entry can unload while the notify platform sets this service up
        if self._unloaded:
            return
        if self._registry is None:
            self._registry = self.hass.data.setdefault(_LEGACY_SERVICES, {}).setdefault(
                self._service_name, []
            )
            self._registry.append(self)
        if self.hass.services.has_service(NOTIFY_DOMAIN, self._service_name):
            return
        self._owns_action = True
        await super().async_register_services()

    @override
    async def async_unregister_services(self) -> None:
        """Remove the action, only if this service registered it."""
        if not self._owns_action:
            return
        self._owns_action = False
        await super().async_unregister_services()

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
