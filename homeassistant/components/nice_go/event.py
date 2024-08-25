"""Nice G.O. event platform."""

import logging
from typing import Any

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NiceGOConfigEntry
from .entity import NiceGOEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: NiceGOConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Nice G.O. event."""

    coordinator = config_entry.runtime_data

    async_add_entities(
        NiceGOEventEntity(coordinator, device_id, device_data.name)
        for device_id, device_data in coordinator.data.items()
    )


EVENT_BARRIER_OBSTRUCTED = "barrier_obstructed"


class NiceGOEventEntity(NiceGOEntity, EventEntity):
    """Event for Nice G.O. devices."""

    _attr_translation_key = "barrier_obstructed"
    _attr_event_types = [EVENT_BARRIER_OBSTRUCTED]

    async def async_added_to_hass(self) -> None:
        """Listen for events."""
        await super().async_added_to_hass()
        self.coordinator.api.event(self.on_barrier_obstructed)

    async def on_barrier_obstructed(self, data: dict[str, Any]) -> None:
        """Handle barrier obstructed event."""
        _LOGGER.debug("Barrier obstructed event: %s", data)
        if data["deviceId"] == self.data.id:
            _LOGGER.debug("Barrier obstructed event for %s, triggering", self.data.name)
            self._trigger_event(EVENT_BARRIER_OBSTRUCTED)
            self.async_write_ha_state()
