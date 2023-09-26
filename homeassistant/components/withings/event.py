"""Events for Withings."""
from __future__ import annotations

from withings_api.common import NotifyAppli

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

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


class WithingsSleepEvent(EventEntity):
    """Representation of a Withings sleep event."""

    _attr_has_entity_name = True
    _attr_event_types = [EVENT_IN_BED, EVENT_OUT_BED]
    _attr_translation_key = "sleep"

    def __init__(self, user_id: str) -> None:
        """Initialize the Withings event entity."""
        self._attr_unique_id = f"{user_id}_sleep"
        self._user_id = user_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, user_id)},
            manufacturer="Withings",
        )

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, f"withings_{self._user_id}_sleep", self.handle_event
            )
        )

    @callback
    def handle_event(self, notification_type: NotifyAppli) -> None:
        """Handle received event."""
        self._trigger_event(APPLI_TO_EVENT[notification_type])
        self.async_write_ha_state()
