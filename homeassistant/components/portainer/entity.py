"""Base class for Portainer entities."""

from pyportainer.models.docker import DockerContainer
from yarl import URL

from homeassistant.const import CONF_URL
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
            configuration_url=URL(
                f"{coordinator.config_entry.data[CONF_URL]}#!/{self.device_id}/docker/dashboard"
            ),
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

        # Container ID's are ephemeral, so use the container name for the unique ID
        # The first one, should always be unique, it's fine if users have aliases
        # According to Docker's API docs, the first name is unique
        assert self._device_info.names, "Container names list unexpectedly empty"
        self.device_name = self._device_info.names[0].replace("/", " ").strip()

        self._attr_device_info = DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    f"{self.coordinator.config_entry.entry_id}_{self.endpoint_id}_{self.device_name}",
                )
            },
            manufacturer=DEFAULT_NAME,
            configuration_url=URL(
                f"{coordinator.config_entry.data[CONF_URL]}#!/{self.endpoint_id}/docker/containers/{self.device_id}"
            ),
            model="Container",
            name=self.device_name,
            via_device=(
                DOMAIN,
                f"{self.coordinator.config_entry.entry_id}_{self.endpoint_id}",
            ),
            translation_key=None if self.device_name else "unknown_container",
        )
