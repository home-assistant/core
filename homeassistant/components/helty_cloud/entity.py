"""Base entity for the Helty Flow Cloud integration."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HeltyCloudDataUpdateCoordinator


class HeltyCloudEntity(CoordinatorEntity[HeltyCloudDataUpdateCoordinator]):
    """Common base for the entities of one VMC."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: HeltyCloudDataUpdateCoordinator) -> None:
        """Initialize the entity and its shared device info."""
        super().__init__(coordinator)
        device = coordinator.device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.serial_number)},
            manufacturer="Helty",
            model=device.model,
            name=device.name,
            serial_number=device.serial_number,
            sw_version=device.firmware,
        )
