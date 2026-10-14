"""Base entities for the HAVEN IAQ integration."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_MODEL, DOMAIN, MANUFACTURER
from .coordinator import HavenDataUpdateCoordinator


class HavenEntity(CoordinatorEntity[HavenDataUpdateCoordinator]):
    """Represent a HAVEN device entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: HavenDataUpdateCoordinator) -> None:
        """Initialize a HAVEN entity."""
        super().__init__(coordinator)
        info = coordinator.info
        model = info.model or DEFAULT_MODEL
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, info.serial_number)},
            manufacturer=info.manufacturer or MANUFACTURER,
            model=model,
            name=f"{model} {info.serial_number}",
            serial_number=info.serial_number,
            sw_version=info.firmware_version,
            hw_version=info.hardware_version,
        )
