"""Base class for Portainer entities."""

from pyportainer.models.docker import DockerContainer

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import PortainerConfigEntry
from .const import DEFAULT_NAME, DOMAIN
from .coordinator import PortainerCoordinator, PortainerCoordinatorData


class PortainerCoordinatorEntity(CoordinatorEntity[PortainerCoordinator]):
    """Base class for Portainer entities."""

    _attr_has_entity_name = True


class PortainerEndpointEntity(PortainerCoordinatorEntity):
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
            model="Endpoint",
            name=self._device_info.endpoint.name,
        )


class PortainerContainerEntity(PortainerCoordinatorEntity):
    """Base implementation for Portainer container."""

    def __init__(
        self,
        device_info: DockerContainer,
        entry: PortainerConfigEntry,
        coordinator: PortainerCoordinator,
        via_device: PortainerCoordinatorData,
    ) -> None:
        """Initialize a Portainer container."""
        super().__init__(coordinator)
        self._device_info = device_info
        self.device_id = self._device_info.id
        self.endpoint_id = via_device.endpoint.id

        self.device_name = (
            self._device_info.names[0].replace("/", " ")
            if self._device_info.names
            else "Unknown Container"
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{self.device_id}")},
            manufacturer=DEFAULT_NAME,
            model="Container",
            name=self.device_name,
            via_device=(
                DOMAIN,
                f"{entry.entry_id}_{self.endpoint_id}",
            ),
        )
