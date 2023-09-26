"""Events for Withings."""
from __future__ import annotations

from withings_api.common import NotifyAppli

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import WithingsEntity

EVENT_IN_BED = "in_bed"
EVENT_OUT_BED = "out_bed"

APPLI_TO_EVENT = {
    NotifyAppli.BED_IN: EVENT_IN_BED,
    NotifyAppli.BED_OUT: EVENT_OUT_BED,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Withings event platform."""
    user_id = str(config_entry.unique_id)

    async_add_entities([WithingsSleepEvent(user_id)])


class WithingsSleepEvent(WithingsEntity, EventEntity):
    """Representation of a Withings sleep event."""

    _attr_event_types = [EVENT_IN_BED, EVENT_OUT_BED]
    _attr_translation_key = "sleep"

    def __init__(self, user_id: str) -> None:
        """Initialize the Withings event entity."""
        super().__init__(user_id)
        self._attr_unique_id = f"{user_id}_sleep"
        self._user_id = user_id

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.hass.bus.async_listen(f"withings_{self._user_id}_sleep", self.handle_event)

    @callback
    def handle_event(self, event: Event) -> None:
        """Handle received event."""
        self._trigger_event(APPLI_TO_EVENT[event.data["type"]])
        self.async_write_ha_state()
