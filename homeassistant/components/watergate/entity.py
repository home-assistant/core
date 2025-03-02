"""Watergate Base Entity Definition."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import WatergateDataCoordinator


class WatergateEntity(CoordinatorEntity[WatergateDataCoordinator]):
    """Define a base Watergate entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: WatergateDataCoordinator,
        entity_name: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._api_client = coordinator.api
        self._attr_unique_id = f"{coordinator.data.state.serial_number}.{entity_name}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.data.state.serial_number)},
            name="Sonic",
            serial_number=coordinator.data.state.serial_number,
            manufacturer=MANUFACTURER,
            sw_version=(
                coordinator.data.state.firmware_version if coordinator.data else None
            ),
        )
