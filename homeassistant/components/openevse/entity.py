"""Base entity for OpenEVSE."""

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OpenEVSEDataUpdateCoordinator


class OpenEVSEEntity(CoordinatorEntity[OpenEVSEDataUpdateCoordinator]):
    """Base implementation for OpenEVSE entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: OpenEVSEDataUpdateCoordinator,
        description: EntityDescription,
        identifier: str,
        unique_id: str | None,
    ) -> None:
        """Initialize the OpenEVSE entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{identifier}-{description.key}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, identifier)},
            manufacturer="OpenEVSE",
        )
        if unique_id:
            self._attr_device_info.connections = {(CONNECTION_NETWORK_MAC, unique_id)}
            self._attr_device_info.serial_number = unique_id
