"""Base entities for LinknLink."""

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DISPLAY_MODEL, DOMAIN
from .coordinator import LinknLinkCoordinator


class LinknLinkEntity(CoordinatorEntity[LinknLinkCoordinator]):
    """Base class for LinknLink entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LinknLinkCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize a LinknLink entity."""
        super().__init__(coordinator)
        self.entity_description = description
        device = coordinator.device
        self._attr_unique_id = f"{device.id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, device.mac)},
            identifiers={(DOMAIN, device.id)},
            manufacturer="LinknLink",
            model=DISPLAY_MODEL,
            name=DISPLAY_MODEL,
            serial_number=device.mac,
        )
