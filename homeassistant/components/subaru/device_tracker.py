"""Support for Subaru device tracker."""

from typing import Any, override

from subarulink.const import LATITUDE, LONGITUDE, TIMESTAMP

from homeassistant.components.device_tracker import TrackerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import VEHICLE_HAS_REMOTE_SERVICE, VEHICLE_STATUS
from .coordinator import SubaruConfigEntry, SubaruDataUpdateCoordinator
from .entity import SubaruCoordinatorEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SubaruConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Subaru device tracker by config_entry."""
    coordinator = config_entry.runtime_data.coordinator
    vehicle_info = config_entry.runtime_data.vehicles
    async_add_entities(
        SubaruDeviceTracker(vehicle, coordinator)
        for vehicle in vehicle_info.values()
        if vehicle[VEHICLE_HAS_REMOTE_SERVICE]
    )


class SubaruDeviceTracker(SubaruCoordinatorEntity, TrackerEntity):
    """Class for Subaru device tracker."""

    _attr_translation_key = "location"
    _attr_name = None

    def __init__(
        self, vehicle_info: dict, coordinator: SubaruDataUpdateCoordinator
    ) -> None:
        """Initialize the device tracker."""
        super().__init__(vehicle_info, coordinator, "location")

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return entity specific state attributes."""
        return {
            "Position timestamp": self.coordinator.data[self.vin][VEHICLE_STATUS].get(
                TIMESTAMP
            )
        }

    @property
    @override
    def latitude(self) -> float | None:
        """Return latitude value of the vehicle."""
        return self.coordinator.data[self.vin][VEHICLE_STATUS].get(LATITUDE)

    @property
    @override
    def longitude(self) -> float | None:
        """Return longitude value of the vehicle."""
        return self.coordinator.data[self.vin][VEHICLE_STATUS].get(LONGITUDE)

    @property
    @override
    def available(self) -> bool:
        """Return if entity is available.

        Adds a check on top of the base availability that at least one of
        the lat/long/timestamp keys is present in vehicle_status — without
        any of these the location entity has nothing meaningful to report.
        """
        if not super().available:
            return False
        status = self.coordinator.data[self.vin].get(VEHICLE_STATUS) or {}
        return bool(status.keys() & {LATITUDE, LONGITUDE, TIMESTAMP})
