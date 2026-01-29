"""Base class for Aladdin Connect entities."""

from genie_partner_sdk.client import AladdinConnectClient

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AladdinConnectCoordinator


class AladdinConnectEntity(CoordinatorEntity[AladdinConnectCoordinator]):
    """Defines a base Aladdin Connect entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AladdinConnectCoordinator) -> None:
        """Initialize Aladdin Connect entity."""
        super().__init__(coordinator)
        device = coordinator.data
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.unique_id)},
            manufacturer="Aladdin Connect",
            name=device.name,
        )
        self._device_id = device.device_id
        self._number = device.door_number

    @property
    def client(self) -> AladdinConnectClient:
        """Return the client for this entity."""
        return self.coordinator.client
