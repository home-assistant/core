"""Base entity for the HP Printer integration."""

from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HpPrinterDataUpdateCoordinator


class HpPrinterEntity(CoordinatorEntity[HpPrinterDataUpdateCoordinator]):
    """Base class for all HP Printer entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: HpPrinterDataUpdateCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        # The config flow only creates entries for printers reporting a serial.
        serial_number = coordinator.config_entry.unique_id
        if TYPE_CHECKING:
            assert serial_number is not None

        device = coordinator.data.device
        model = device.make_and_model if device else None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial_number)},
            configuration_url=coordinator.client.base_url,
            manufacturer="HP",
            model=model,
            model_id=device.product_number if device else None,
            name=model or coordinator.config_entry.title,
            serial_number=serial_number,
        )
