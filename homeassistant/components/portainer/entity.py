"""Base class for Portainer entities."""

from pyportainer.models.docker import DockerContainer

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

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
        coordinator: PortainerCoordinator,
    ) -> None:
        """Initialize a Portainer endpoint."""
        super().__init__(coordinator)
        self._device_info = device_info
        self.device_id = device_info.endpoint.id
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, f"{coordinator.config_entry.entry_id}_{self.device_id}")
            },
            manufacturer=DEFAULT_NAME,
            model="Endpoint",
            name=device_info.endpoint.name,
        )


class PortainerContainerEntity(PortainerCoordinatorEntity):
    """Base implementation for Portainer container."""

    def __init__(
        self,
        device_info: DockerContainer,
        coordinator: PortainerCoordinator,
        via_device: PortainerCoordinatorData,
    ) -> None:
        """Initialize a Portainer container."""
        super().__init__(coordinator)
        self._device_info = device_info
        self.device_id = self._device_info.id
        self.endpoint_id = via_device.endpoint.id

        device_name = (
            self._device_info.names[0].replace("/", " ").strip()
            if self._device_info.names
            else None
        )

        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, f"{self.coordinator.config_entry.entry_id}_{device_name}")
            },
            manufacturer=DEFAULT_NAME,
            model="Container",
            name=device_name,
            via_device=(
                DOMAIN,
                f"{self.coordinator.config_entry.entry_id}_{self.endpoint_id}",
            ),
            translation_key=None if device_name else "unknown_container",
        )
