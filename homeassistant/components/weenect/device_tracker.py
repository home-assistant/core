"""Device tracker platform for weenect."""
from __future__ import annotations

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, TRACKER_ADDED
from .entity import WeenectBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the weenect device_trackers."""

    coordinator = hass.data[DOMAIN][entry.entry_id]

    @callback
    def async_add_device_trackers(
        added: list[int],
    ) -> None:
        """Add device_trackers callback."""

        trackers: list = []
        for tracker_id in added:
            trackers.append(
                WeenectDeviceTracker(
                    coordinator,
                    tracker_id,
                )
            )

        async_add_entities(trackers, True)

    unsub_dispatcher = async_dispatcher_connect(
        hass,
        f"{entry.entry_id}_{TRACKER_ADDED}",
        async_add_device_trackers,
    )
    coordinator.unsub_dispatchers.append(unsub_dispatcher)
    if len(coordinator.data) > 0:
        async_add_device_trackers(coordinator.data.keys())


class WeenectDeviceTracker(WeenectBaseEntity, TrackerEntity):
    """weenect device tracker."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        tracker_id: int,
    ) -> None:
        """Init Device Tracker."""
        super().__init__(coordinator, tracker_id)
        self._attr_icon = "mdi:paw"
        self._attr_unique_id = f"{self.coordinator.config_entry.entry_id}_{tracker_id}"
        self._attr_name = self.coordinator.data[self.id]["name"]

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and bool(self.coordinator.data[self.id]["position"])

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the device."""
        if self.id in self.coordinator.data:
            if self.coordinator.data[self.id]["position"]:
                return self.coordinator.data[self.id]["position"][0]["latitude"]
        return None

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        if self.id in self.coordinator.data:
            if self.coordinator.data[self.id]["position"]:
                return self.coordinator.data[self.id]["position"][0]["longitude"]
        return None

    @property
    def source_type(self) -> SourceType:
        """Return the source type, eg gps or router, of the device."""
        return SourceType.GPS

    @property
    def location_accuracy(self) -> int:
        """Return the location accuracy of the device.

        Value in meters.
        """
        if self.id in self.coordinator.data:
            if self.coordinator.data[self.id]["position"]:
                return self.coordinator.data[self.id]["position"][0]["radius"]
        return 0
