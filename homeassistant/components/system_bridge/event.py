"""Support for System Bridge notification events."""

from typing import TYPE_CHECKING, override

from packaging.version import parse as parse_version
from systembridgeconnector.models.notification import NotificationEvent

from homeassistant.components.event import EventEntity
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import NOTIFICATION_EVENTS_MIN_VERSION, SIGNAL_NOTIFICATION_EVENT
from .coordinator import SystemBridgeConfigEntry
from .entity import SystemBridgeEntity

PARALLEL_UPDATES = 0

EVENT_CLICKED = "clicked"
EVENT_CLOSED = "closed"
EVENT_SENT = "sent"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SystemBridgeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up System Bridge event based on a config entry."""
    coordinator = entry.runtime_data
    system = coordinator.data.system
    if TYPE_CHECKING:
        assert system is not None

    if (
        system.version is None
        or parse_version(system.version).release < NOTIFICATION_EVENTS_MIN_VERSION
    ):
        return

    async_add_entities(
        [
            SystemBridgeNotificationEventEntity(
                coordinator, entry.data[CONF_PORT], "notification"
            )
        ]
    )


class SystemBridgeNotificationEventEntity(SystemBridgeEntity, EventEntity):
    """Representation of a System Bridge notification event entity."""

    _attr_event_types = [EVENT_SENT, EVENT_CLICKED, EVENT_CLOSED]
    _attr_translation_key = "notification"

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to notification events."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_NOTIFICATION_EVENT.format(
                    self.coordinator.config_entry.entry_id
                ),
                self._async_handle_event,
            )
        )

    @callback
    def _async_handle_event(self, event: NotificationEvent) -> None:
        """Handle a notification being sent, clicked or closed."""
        if event.action is not None:
            self._trigger_event(
                EVENT_CLICKED,
                {"notification_id": event.id, "action": event.action},
            )
        elif event.reason is not None:
            self._trigger_event(
                EVENT_CLOSED,
                {"notification_id": event.id, "reason": event.reason},
            )
        else:
            # A sent notification has neither, and has what was sent instead
            self._trigger_event(
                EVENT_SENT,
                {
                    "notification_id": event.id,
                    "title": event.title,
                    "message": event.message,
                    "buttons": [
                        {"id": button.id, "label": button.label}
                        for button in event.buttons or []
                    ],
                },
            )
        self.async_write_ha_state()
