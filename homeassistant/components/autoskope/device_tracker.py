"""Support for Autoskope device tracking."""

from __future__ import annotations

from autoskope_client.constants import MANUFACTURER
from autoskope_client.models import Vehicle
from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AutoskopeConfigEntry, AutoskopeDataUpdateCoordinator

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AutoskopeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Autoskope device tracker entities."""
    coordinator: AutoskopeDataUpdateCoordinator = entry.runtime_data
    tracked_vehicles: set[str] = set()

    @callback
    def update_entities() -> None:
        """Update entities based on coordinator data."""
        current_vehicles = set(coordinator.data.keys())
        vehicles_to_add = current_vehicles - tracked_vehicles

        if vehicles_to_add:
            new_entities = [
                AutoskopeDeviceTracker(coordinator, vehicle_id)
                for vehicle_id in vehicles_to_add
            ]
            tracked_vehicles.update(vehicles_to_add)
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(update_entities))
    update_entities()


class AutoskopeDeviceTracker(
    CoordinatorEntity[AutoskopeDataUpdateCoordinator], TrackerEntity
):
    """Representation of an Autoskope tracked device."""

    _attr_has_entity_name = True
    _attr_name: str | None = None

    def __init__(
        self, coordinator: AutoskopeDataUpdateCoordinator, vehicle_id: str
    ) -> None:
        """Initialize the TrackerEntity."""
        super().__init__(coordinator)
        self._vehicle_id = vehicle_id
        self._attr_unique_id = vehicle_id

        # Set device info from coordinator data
        vehicle_data = coordinator.data[vehicle_id]
        self._attr_device_info = DeviceInfo(  # type: ignore[assignment]
            identifiers={(DOMAIN, str(vehicle_data.id))},
            name=vehicle_data.name,
            manufacturer=MANUFACTURER,
            model=vehicle_data.model,
            serial_number=vehicle_data.imei,  # IMEI is the device serial number
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available
            and self.coordinator.data is not None
            and self._vehicle_id in self.coordinator.data
        )

    @property
    def _vehicle_data(self) -> Vehicle | None:
        """Return the vehicle data for the current entity."""
        return self.coordinator.data.get(self._vehicle_id)

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the device."""
        if (vehicle := self._vehicle_data) and vehicle.position:
            return float(vehicle.position.latitude)
        return None

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        if (vehicle := self._vehicle_data) and vehicle.position:
            return float(vehicle.position.longitude)
        return None

    @property
    def source_type(self) -> SourceType:
        """Return the source type of the device."""
        return SourceType.GPS

    @property
    def location_accuracy(self) -> int:
        """Return the location accuracy of the device in meters."""
        if (vehicle := self._vehicle_data) and vehicle.gps_quality:
            if vehicle.gps_quality > 0:
                # HDOP to estimated accuracy in meters
                # HDOP of 1-2 = good (5-10m), 2-5 = moderate (10-25m), >5 = poor (>25m)
                return max(5, int(vehicle.gps_quality * 5.0))
        return 0

    @property
    def icon(self) -> str:
        """Return the icon based on the vehicle's activity."""
        if (vehicle := self._vehicle_data) and vehicle.position:
            if vehicle.position.park_mode:
                return "mdi:car-brake-parking"
            if vehicle.position.speed > 5:  # Moving threshold: 5 km/h
                return "mdi:car-arrow-right"
            return "mdi:car"
        return "mdi:car-clock"
