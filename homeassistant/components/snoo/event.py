"""Support for Snoo Events."""

from homeassistant.components.event import EventEntity, EventEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SnooConfigEntry
from .entity import SnooDescriptionEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SnooConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Snoo device."""
    coordinators = entry.runtime_data
    async_add_entities(
        SnooEvent(
            coordinator,
            EventEntityDescription(
                key="event",
                translation_key="event",
                event_types=[
                    "timer",
                    "cry",
                    "command",
                    "safety_clip",
                    "long_activity_press",
                    "activity",
                    "power",
                    "status_requested",
                    "sticky_white_noise_updated",
                    "config_change",
                ],
            ),
        )
        for coordinator in coordinators.values()
    )


class SnooEvent(SnooDescriptionEntity, EventEntity):
    """A event using Snoo coordinator."""

    @callback
    def _async_handle_event(self) -> None:
        """Handle the demo button event."""
        self._trigger_event(
            self.coordinator.data.event.value,
        )
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Add Event."""
        await super().async_added_to_hass()
        if self.coordinator.data:
            # If we were able to get data on startup - set it
            # Otherwise, it will update when the coordinator gets data.
            self._async_handle_event()

    def _handle_coordinator_update(self) -> None:
        self._async_handle_event()
        return super()._handle_coordinator_update()
