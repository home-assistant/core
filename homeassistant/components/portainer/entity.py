"""Base class for Portainer entities."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import PortainerConfigEntry
from .const import DEFAULT_NAME, DOMAIN
from .coordinator import PortainerCoordinator, PortainerCoordinatorData


class ProtainerCoordinatorEntity(CoordinatorEntity[PortainerCoordinator]):
    """Base class for Portainer entities."""

    _attr_has_entity_name = True


class PortainerEndpointEntity(ProtainerCoordinatorEntity):
    """Base implementation for Portainer endpoint."""

    def __init__(
        self,
        device_info: PortainerCoordinatorData,
        entry: PortainerConfigEntry,
        coordinator: PortainerCoordinator,
    ) -> None:
        """Initialize a Portainer endpoint."""
        super().__init__(coordinator)
        self._device_info = device_info
        self.device_id = self._device_info.endpoint.id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{self.device_id}")},
            manufacturer=DEFAULT_NAME,
            model="Portainer",
            name=self._device_info.endpoint.name,
        )
