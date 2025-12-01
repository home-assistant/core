"""Define the Brother entity."""

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BrotherDataUpdateCoordinator


class BrotherPrinterEntity(CoordinatorEntity[BrotherDataUpdateCoordinator]):
    """Define a Brother Printer entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BrotherDataUpdateCoordinator,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            configuration_url=f"http://{coordinator.brother.host}/",
            identifiers={(DOMAIN, coordinator.brother.serial)},
            connections={(CONNECTION_NETWORK_MAC, coordinator.brother.mac)},
            serial_number=coordinator.brother.serial,
            manufacturer="Brother",
            model_id=coordinator.brother.model,
            name=coordinator.brother.model,
            sw_version=coordinator.brother.firmware,
        )
