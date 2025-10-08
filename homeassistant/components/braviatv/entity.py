"""A entity class for Bravia TV integration."""

from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_MANUFACTURER, DOMAIN
from .coordinator import BraviaTVCoordinator


class BraviaTVEntity(CoordinatorEntity[BraviaTVCoordinator]):
    """BraviaTV entity class."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: BraviaTVCoordinator, unique_id: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)

        self._attr_unique_id = unique_id

        if TYPE_CHECKING:
            assert coordinator.client.mac is not None

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            connections={(CONNECTION_NETWORK_MAC, coordinator.client.mac)},
            manufacturer=ATTR_MANUFACTURER,
            model_id=coordinator.system_info.get("model"),
            hw_version=coordinator.system_info.get("generation"),
            serial_number=coordinator.system_info.get("serial"),
        )
