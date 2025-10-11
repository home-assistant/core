"""Event platform for foscam integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.event import EventEntity, EventEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_WEBHOOK_ID, DOMAIN, EVENT, MAP_EVENTS
from .coordinator import FoscamConfigEntry, FoscamCoordinator
from .entity import FoscamEntity


@dataclass(kw_only=True, frozen=True)
class FoscamEventEntityDescription(EventEntityDescription):
    """Sleep as Android sensor description."""


EVENT_DESCRIPTIONS: list[FoscamEventEntityDescription] = [
    FoscamEventEntityDescription(
        key="motion_detect_event",
        translation_key="motion_detect_event",
        event_types=[
            "Motion detection alarm",
            "Human detection alarm",
            "Facial detection alarm",
            "Vehicle detection alarm",
            "Pet detection alarm",
        ],
    ),
    FoscamEventEntityDescription(
        key="sound_detect_event",
        translation_key="sound_detect_event",
        event_types=["Sound detection alarm"],
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FoscamConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the foscam event platform."""
    coordinator = config_entry.runtime_data

    async_add_entities(
        FoscamEventEntity(coordinator, description)
        for description in EVENT_DESCRIPTIONS
    )


class FoscamEventEntity(FoscamEntity, EventEntity):
    """foscam event entity."""

    entity_description: FoscamEventEntityDescription

    def __init__(
        self,
        coordinator: FoscamCoordinator,
        description: FoscamEventEntityDescription,
    ) -> None:
        """Initialize the data."""

        entry_id = coordinator.config_entry.entry_id
        super().__init__(coordinator, entry_id)

        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self.webhook_id = coordinator.config_entry.data[CONF_WEBHOOK_ID]
        self._disconnect_dispatcher = async_dispatcher_connect(
            coordinator.hass,
            DOMAIN,
            self._async_handle_event,
        )

    @callback
    def _async_handle_event(self, webhook_id: str, data: dict[str, str]) -> None:
        """Handle the foscam event."""
        event = MAP_EVENTS.get(data[EVENT], data[EVENT])
        if (
            webhook_id == self.webhook_id
            and self.entity_description.event_types is not None
            and event in self.entity_description.event_types
        ):
            self._trigger_event(event)
            self.async_write_ha_state()
