"""Device tracker platform for LoJack integration."""

from __future__ import annotations

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import LoJackConfigEntry
from .const import DOMAIN
from .coordinator import LoJackCoordinator, get_device_name

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LoJackConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LoJack device tracker from a config entry."""
    async_add_entities(
        LoJackDeviceTracker(coordinator)
        for coordinator in entry.runtime_data.coordinators
    )


class LoJackDeviceTracker(CoordinatorEntity[LoJackCoordinator], TrackerEntity):
    """Representation of a LoJack device tracker."""

    _attr_has_entity_name = True
    _attr_name = None  # Main entity of the device, uses device name directly

    def __init__(self, coordinator: LoJackCoordinator) -> None:
        """Initialize the device tracker."""
        super().__init__(coordinator)
        self._attr_unique_id = coordinator.vehicle.id

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.vehicle.id)},
            name=get_device_name(self.coordinator.vehicle),
            manufacturer="Spireon LoJack",
            model=self.coordinator.vehicle.model,
            serial_number=self.coordinator.vehicle.vin,
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
