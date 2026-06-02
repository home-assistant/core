"""Base class for Aladdin Connect entities."""

from genie_partner_sdk.client import AladdinConnectClient
from genie_partner_sdk.model import GarageDoor

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AladdinConnectCoordinator


class AladdinConnectEntity(CoordinatorEntity[AladdinConnectCoordinator]):
    """Defines a base Aladdin Connect entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AladdinConnectCoordinator, door_id: str) -> None:
        """Initialize Aladdin Connect entity."""
        super().__init__(coordinator)
        self._door_id = door_id
        door = self.door
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, door.unique_id)},
            manufacturer="Aladdin Connect",
            name=door.name,
        )
        self._device_id = door.device_id
        self._number = door.door_number

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._door_id in self.coordinator.data

    @property
    def door(self) -> GarageDoor:
        """Return the garage door data."""
        return self.coordinator.data[self._door_id]

    @property
    def client(self) -> AladdinConnectClient:
        """Return the client for this entity."""
        return self.coordinator.client
