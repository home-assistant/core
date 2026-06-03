"""Support for SwitchBot event entities."""

from dataclasses import dataclass

from homeassistant.components.event import (
    EventDeviceClass,
    EventEntity,
    EventEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SwitchbotConfigEntry, SwitchbotDataUpdateCoordinator
from .entity import SwitchbotEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class SwitchbotEventEntityDescription(EventEntityDescription):
    """Describes a Switchbot event entity."""

    counter_key: str
    fire_event: str


EVENT_DESCRIPTIONS: tuple[SwitchbotEventEntityDescription, ...] = (
    SwitchbotEventEntityDescription(
        key="doorbell",
        device_class=EventDeviceClass.DOORBELL,
        event_types=["ring"],
        counter_key="doorbell_seq",
        fire_event="ring",
    ),
    SwitchbotEventEntityDescription(
        key="button",
        device_class=EventDeviceClass.BUTTON,
        event_types=["press"],
        counter_key="button_count",
        fire_event="press",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SwitchbotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SwitchBot event platform."""
    coordinator = config_entry.runtime_data
    async_add_entities(
        SwitchbotEventEntity(coordinator, description)
        for description in EVENT_DESCRIPTIONS
        if description.counter_key in coordinator.device.parsed_data
    )


class SwitchbotEventEntity(SwitchbotEntity, EventEntity):
    """Representation of a SwitchBot event."""

    entity_description: SwitchbotEventEntityDescription

    def __init__(
        self,
        coordinator: SwitchbotDataUpdateCoordinator,
        description: SwitchbotEventEntityDescription,
    ) -> None:
        """Initialize the SwitchBot event."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.base_unique_id}-{description.key}"
        self._previous_counter = int(
            coordinator.device.parsed_data.get(description.counter_key, 0)
        )

    @callback
    def _async_update_attrs(self) -> None:
        """Update the entity attributes."""
        counter = int(self.parsed_data.get(self.entity_description.counter_key, 0))
        if counter not in (0, self._previous_counter):
            self._trigger_event(self.entity_description.fire_event)
        self._previous_counter = counter
