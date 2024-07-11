"""Support for Tractive device trackers."""

from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

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
    async_add_entities: AddEntitiesCallback,
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
        self._latitude: float = item.pos_report["latlong"][0]
        self._longitude: float = item.pos_report["latlong"][1]
        self._accuracy: int = item.pos_report["pos_uncertainty"]
        self._source_type: str = item.pos_report["sensor_used"]
        self._attr_unique_id = item.trackable["_id"]

    @property
    def source_type(self) -> SourceType:
        """Return the source type, eg gps or router, of the device."""
        if self._source_type == "PHONE":
            return SourceType.BLUETOOTH
        if self._source_type == "KNOWN_WIFI":
            return SourceType.ROUTER
        return SourceType.GPS

    @property
    def latitude(self) -> float:
        """Return latitude value of the device."""
        return self._latitude

    @property
    def longitude(self) -> float:
        """Return longitude value of the device."""
        return self._longitude

    @property
    def location_accuracy(self) -> int:
        """Return the gps accuracy of the device."""
        return self._accuracy

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
        self._latitude = event["latitude"]
        self._longitude = event["longitude"]
        self._accuracy = event["accuracy"]
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
