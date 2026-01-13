"""fressnapf_tracker class."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import FressnapfTrackerDataUpdateCoordinator
from .const import DOMAIN


class FressnapfTrackerBaseEntity(
    CoordinatorEntity[FressnapfTrackerDataUpdateCoordinator]
):
    """Base entity for Fressnapf Tracker."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: FressnapfTrackerDataUpdateCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.id = coordinator.device.serialnumber
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(self.id))},
            name=str(self.coordinator.data.name),
            model=str(self.coordinator.data.tracker_settings.generation),
            manufacturer="Fressnapf",
            serial_number=str(self.id),
        )


class FressnapfTrackerEntity(FressnapfTrackerBaseEntity):
    """Entity for fressnapf_tracker."""

    def __init__(
        self,
        coordinator: FressnapfTrackerDataUpdateCoordinator,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{self.id}_{entity_description.key}"
