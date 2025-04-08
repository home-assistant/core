"""Support for Overseerr events."""

from dataclasses import dataclass
from typing import Any

from homeassistant.components.event import EventEntity, EventEntityDescription
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DOMAIN, EVENT_KEY
from .const import ISSUE_EVENT_TYPES, MEDIA_EVENT_TYPES
from .coordinator import OverseerrConfigEntry, OverseerrCoordinator
from .entity import OverseerrEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class OverseerrEventEntityDescription(EventEntityDescription):
    """Describes Overseerr config event entity."""

    nullable_fields: list[str]


EVENTS: tuple[OverseerrEventEntityDescription, ...] = (
    OverseerrEventEntityDescription(
        key="media",
        translation_key="last_media_event",
        event_types=[
            MEDIA_EVENT_TYPES["pending"],
            MEDIA_EVENT_TYPES["approved"],
            MEDIA_EVENT_TYPES["available"],
            MEDIA_EVENT_TYPES["failed"],
            MEDIA_EVENT_TYPES["declined"],
            MEDIA_EVENT_TYPES["auto_approved"],
        ],
        nullable_fields=["comment", "issue"],
    ),
    OverseerrEventEntityDescription(
        key="issue",
        translation_key="last_issue_event",
        event_types=[
            ISSUE_EVENT_TYPES["reported"],
            ISSUE_EVENT_TYPES["commented"],
            ISSUE_EVENT_TYPES["resolved"],
            ISSUE_EVENT_TYPES["reopened"],
        ],
        nullable_fields=["comment"],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OverseerrConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Overseerr sensor entities based on a config entry."""

    coordinator = entry.runtime_data
    ent_reg = er.async_get(hass)

    event_entities_setup_before = ent_reg.async_get_entity_id(
        Platform.EVENT, DOMAIN, f"{entry.entry_id}-media"
    )

    if coordinator.push or event_entities_setup_before:
        async_add_entities(
            OverseerrEvent(coordinator, description) for description in EVENTS
        )


class OverseerrEvent(OverseerrEntity, EventEntity):
    """Defines a Overseerr event entity."""

    entity_description: OverseerrEventEntityDescription

    def __init__(
        self,
        coordinator: OverseerrCoordinator,
        description: OverseerrEventEntityDescription,
    ) -> None:
        """Initialize Overseerr event entity."""
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._attr_available = True

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(self.hass, EVENT_KEY, self._handle_update)
        )

    async def _handle_update(self, event: dict[str, Any]) -> None:
        """Handle incoming event."""
        event_type = event["notification_type"].lower()
        if event_type.split("_")[0] == self.entity_description.key:
            self._attr_entity_picture = event.get("image")
            self._trigger_event(
                event_type[6:],
                parse_event(event, self.entity_description.nullable_fields),
            )
            self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        if super().available != self._attr_available:
            self._attr_available = super().available
            super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._attr_available and self.coordinator.push


def parse_event(event: dict[str, Any], nullable_fields: list[str]) -> dict[str, Any]:
    """Parse event."""
    event.pop("image")
    for field in nullable_fields:
        event.pop(field)
    if (media := event.get("media")) is not None:
        for field in ("status", "status4k"):
            media[field] = media[field].lower()
        for field in ("tmdb_id", "tvdb_id"):
            if (value := media.get(field)) != "":
                media[field] = int(value)
            else:
                media[field] = None
    if (request := event.get("request")) is not None:
        request["request_id"] = int(request["request_id"])
    if (issue := event.get("issue")) is not None:
        issue["issue_id"] = int(issue["issue_id"])
    return event
