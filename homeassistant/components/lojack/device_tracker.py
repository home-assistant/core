"""Device tracker platform for LoJack integration."""

from __future__ import annotations

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import LoJackConfigEntry
from .coordinator import LoJackCoordinator, get_device_name
from .const import DOMAIN

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LoJackConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up LoJack device tracker from a config entry."""
    async_add_entities(
        LoJackDeviceTracker(coordinator) for coordinator in entry.runtime_data
    )


class LoJackDeviceTracker(CoordinatorEntity[LoJackCoordinator], TrackerEntity):
    """Representation of a LoJack device tracker."""

    _attr_has_entity_name = True
    _attr_name = None  # Main entity of the device, uses device name directly

    def __init__(self, coordinator: LoJackCoordinator) -> None:
        """Initialize the device tracker."""
        super().__init__(coordinator)
        vehicle = coordinator.data
        self._attr_unique_id = vehicle.device_id
        device_name = get_device_name(vehicle)

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, vehicle.device_id)},
            name=device_name,
            manufacturer="Spireon LoJack",
            model=vehicle.model,
            serial_number=vehicle.vin,
        )

    @property
    def source_type(self) -> SourceType:
        """Return the source type of the device."""
        return SourceType.GPS

    @property
    def latitude(self) -> float | None:
        """Return the latitude of the device."""
        return self.coordinator.data.latitude

    @property
    def longitude(self) -> float | None:
        """Return the longitude of the device."""
        return self.coordinator.data.longitude

    @property
    def location_accuracy(self) -> int:
        """Return the location accuracy of the device."""
        if self.coordinator.data.accuracy is not None:
            return int(self.coordinator.data.accuracy)
        return 0

    @property
    def battery_level(self) -> int | None:
        """Return the battery level of the device (if applicable)."""
        # LoJack devices report vehicle battery voltage, not percentage
        return None
