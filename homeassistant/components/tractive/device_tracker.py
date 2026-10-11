"""Support for Tractive device trackers."""

from typing import Any, override

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import Trackables, TractiveClient, TractiveConfigEntry
from .const import TRACKER_POSITION_UPDATED
from .entity import TractiveEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TractiveConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Tractive device trackers."""
    client = entry.runtime_data.client
    trackables = entry.runtime_data.trackables

    entities = [TractiveDeviceTracker(hass, entry, client, item) for item in trackables]

    async_add_entities(entities)


class TractiveDeviceTracker(TractiveEntity, TrackerEntity):
    """Tractive device tracker."""

    _attr_translation_key = "tracker"
    _attr_name = None

    def __init__(
        self,
        hass: HomeAssistant,
        entry: TractiveConfigEntry,
        client: TractiveClient,
        item: Trackables,
    ) -> None:
        """Initialize tracker entity."""
        super().__init__(
            hass,
            entry,
            client,
            item.trackable,
            item.tracker_details,
            f"{TRACKER_POSITION_UPDATED}-{item.tracker_details['_id']}",
        )

        # A tracker that has been switched off for a while has no position
        pos_report = item.pos_report or {}
        if latlong := pos_report.get("latlong"):
            self._attr_latitude, self._attr_longitude = latlong
        self._attr_location_accuracy: float = pos_report.get("pos_uncertainty") or 0
        self._source_type: str | None = pos_report.get("sensor_used")
        self._attr_unique_id = item.trackable["_id"]

    @property
    @override
    def source_type(self) -> SourceType:
        """Return the source type of the device."""
        if self._source_type == "PHONE":
            return SourceType.BLUETOOTH
        return SourceType.GPS

    @callback
    @override
    def handle_status_update(self, event: dict[str, Any]) -> None:
        """Handle position update."""
        self._attr_latitude = event["latitude"]
        self._attr_longitude = event["longitude"]
        self._attr_location_accuracy = event["accuracy"]
        self._source_type = event["sensor_used"]
        self._attr_available = True
        self.async_write_ha_state()
