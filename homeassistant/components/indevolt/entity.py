"""Base entity for Indevolt integration."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import IndevoltCoordinator


class IndevoltEntity(CoordinatorEntity[IndevoltCoordinator]):
    """Base Indevolt entity with up-to-date device info."""

    _attr_has_entity_name = True

    @property
    def serial_number(self) -> str | None:
        """Return the device serial number."""
        return self.coordinator.device_info_data.get("sn")

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for registry."""
        data = self.coordinator.device_info_data
        return DeviceInfo(
            identifiers={(DOMAIN, data["sn"])},
            manufacturer="INDEVOLT",
            name=f"INDEVOLT {data['device_model']}",
            serial_number=data["sn"],
            model=data["device_model"],
            sw_version=data["fw_version"],
            hw_version=str(data["generation"]),
        )
