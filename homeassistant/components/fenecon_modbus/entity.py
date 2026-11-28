"""Base entity for the Fenecon Modbus integration."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FeneconCoordinator


class FeneconEntity(CoordinatorEntity[FeneconCoordinator]):
    """Base class for Fenecon entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: FeneconCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        # Entries of a FEMS that reports no serial number have no unique ID
        self._device_id = entry.unique_id or entry.entry_id
        info = coordinator.device_info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            manufacturer=info.manufacturer,
            model=info.manufacturer_model,
            serial_number=info.manufacturer_ems_serial_number,
            sw_version=info.openems_version,
        )
