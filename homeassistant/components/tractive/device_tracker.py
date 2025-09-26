"""Support for Tractive device trackers."""

from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import Trackables, TractiveClient, TractiveConfigEntry
from .const import (
    SERVER_UNAVAILABLE,
    TRACKER_HARDWARE_STATUS_UPDATED,
    TRACKER_POSITION_UPDATED,
)
from .entity import TractiveEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TractiveConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Tractive device trackers."""
    client = entry.runtime_data.client
    trackables = entry.runtime_data.trackables

    entities = [TractiveDeviceTracker(client, item) for item in trackables]

    async_add_entities(entities)


class TractiveDeviceTracker(TractiveEntity, TrackerEntity):
    """Tractive device tracker."""

    _attr_translation_key = "tracker"

    def __init__(self, client: TractiveClient, item: Trackables) -> None:
        """Initialize tracker entity."""
        super().__init__(
            client,
            item.trackable,
            item.tracker_details,
            f"{TRACKER_HARDWARE_STATUS_UPDATED}-{item.tracker_details['_id']}",
        )

        self._battery_level: int | None = item.hw_info.get("battery_level")
        self._attr_latitude = item.pos_report["latlong"][0]
        self._attr_longitude = item.pos_report["latlong"][1]
        self._attr_location_accuracy: float = item.pos_report["pos_uncertainty"]
        self._source_type: str = item.pos_report["sensor_used"]
        self._attr_unique_id = item.trackable["_id"]

    @property
    def source_type(self) -> SourceType:
        """Return the source type of the device."""
        if self._source_type == "PHONE":
            return SourceType.BLUETOOTH
        return SourceType.GPS

    @property
    def battery_level(self) -> int | None:
        """Return the battery level of the device."""
        return self._battery_level

    @callback
    def _handle_hardware_status_update(self, event: dict[str, Any]) -> None:
        self._battery_level = event["battery_level"]
        self._attr_available = True
        self.async_write_ha_state()

    @callback
    def _handle_position_update(self, event: dict[str, Any]) -> None:
        self._attr_latitude = event["latitude"]
        self._attr_longitude = event["longitude"]
        self._attr_location_accuracy = event["accuracy"]
        self._source_type = event["sensor_used"]
        self._attr_available = True
        self.async_write_ha_state()

    # pylint: disable-next=hass-missing-super-call
    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        if not self._client.subscribed:
            self._client.subscribe()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self._dispatcher_signal,
                self._handle_hardware_status_update,
            )
        )

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{TRACKER_POSITION_UPDATED}-{self._tracker_id}",
                self._handle_position_update,
            )
        )

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SERVER_UNAVAILABLE}-{self._user_id}",
                self.handle_server_unavailable,
            )
        )
