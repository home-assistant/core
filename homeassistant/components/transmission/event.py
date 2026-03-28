"""Define events for the Transmission integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.event import EventEntity, EventEntityDescription
from homeassistant.const import ATTR_ID, ATTR_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    ATTR_DOWNLOAD_PATH,
    ATTR_LABELS,
    EVENT_TYPE_DOWNLOADED,
    EVENT_TYPE_REMOVED,
    EVENT_TYPE_STARTED,
)
from .coordinator import TransmissionConfigEntry, TransmissionEventData
from .entity import TransmissionEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TransmissionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Transmission event platform."""
    coordinator = config_entry.runtime_data

    description = EventEntityDescription(
        key="torrent",
        translation_key="torrent",
        event_types=[
            EVENT_TYPE_STARTED,
            EVENT_TYPE_DOWNLOADED,
            EVENT_TYPE_REMOVED,
        ],
    )

    async_add_entities([TransmissionEvent(coordinator, description)])


class TransmissionEvent(TransmissionEntity, EventEntity):
    """Representation of a Transmission event entity."""

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()

        if TYPE_CHECKING:
            assert self._attr_unique_id

        self.async_on_remove(
            self.coordinator.async_add_event_listener(
                self._handle_event, self._attr_unique_id
            )
        )

    @callback
    def _handle_event(self, event_data: TransmissionEventData) -> None:
        """Handle the torrent events."""

        event_type = event_data.event_type

        if event_type not in self.event_types:
            _LOGGER.warning("Event type %s is not known", event_type)
            return

        self._trigger_event(
            event_type,
            {
                ATTR_NAME: event_data.name,
                ATTR_ID: event_data.id,
                ATTR_DOWNLOAD_PATH: event_data.download_path,
                ATTR_LABELS: event_data.labels,
            },
        )

        self.async_write_ha_state()
