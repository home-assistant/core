"""Support for Overseerr events."""

from dataclasses import dataclass
from typing import Any

from homeassistant.components.event import EventEntity, EventEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EVENT_KEY
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
            "pending",
            "approved",
            "available",
            "failed",
            "declined",
            "auto_approved",
        ],
        nullable_fields=["comment", "issue"],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OverseerrConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Overseerr sensor entities based on a config entry."""

    coordinator = entry.runtime_data
    async_add_entities(
        OverseerrEvent(coordinator, description) for description in EVENTS
    )


class OverseerrEvent(OverseerrEntity, EventEntity):
    """Defines a Overseerr event entity."""

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
            self._trigger_event(event_type[6:], event)
            self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        if super().available != self._attr_available:
            self._attr_available = super().available
            super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._attr_available


def parse_event(event: dict[str, Any], nullable_fields: list[str]) -> dict[str, Any]:
    """Parse event."""
    event.pop("notification_type")
    for field in nullable_fields:
        event.pop(field)
    return event
