"""Base class for Portainer entities."""

from yarl import URL

from homeassistant.const import CONF_URL
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_NAME, DOMAIN
from .coordinator import (
    PortainerContainerData,
    PortainerCoordinator,
    PortainerCoordinatorData,
    PortainerStackData,
)


class PortainerCoordinatorEntity(CoordinatorEntity[PortainerCoordinator]):
    """Base class for Portainer entities."""

    _attr_has_entity_name = True


class PortainerEndpointEntity(PortainerCoordinatorEntity):
    """Base implementation for Portainer endpoint."""

    def __init__(
        self,
        coordinator: PortainerCoordinator,
        entity_description: EntityDescription,
        device_info: PortainerCoordinatorData,
    ) -> None:
        """Initialize a Portainer endpoint."""
        super().__init__(coordinator)
        self.entity_description = entity_description
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
            entry_type=DeviceEntryType.SERVICE,
        )
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{device_info.id}_{entity_description.key}"

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return super().available and self.device_id in self.coordinator.data


class PortainerContainerEntity(PortainerCoordinatorEntity):
    """Base implementation for Portainer container."""

    def __init__(
        self,
        coordinator: PortainerCoordinator,
        entity_description: EntityDescription,
        device_info: PortainerContainerData,
        via_device: PortainerCoordinatorData,
    ) -> None:
        """Initialize a Portainer container."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._device_info = device_info
        self.device_id = self._device_info.container.id
        self.endpoint_id = via_device.endpoint.id

        # Container ID's are ephemeral, so use the container name for the unique ID
        # The first one, should always be unique, it's fine if users have aliases
        # According to Docker's API docs, the first name is unique
        names = self._device_info.container.names
        assert names, "Container names list unexpectedly empty"
        self.device_name = names[0].replace("/", " ").strip()

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
            # If the container belongs to a stack, nest it under the stack
            # else it's the endpoint
            via_device=(
                DOMAIN,
                f"{coordinator.config_entry.entry_id}_{self.endpoint_id}_stack_{device_info.stack.id}"
                if device_info.stack
                else f"{coordinator.config_entry.entry_id}_{self.endpoint_id}",
            ),
            translation_key=None if self.device_name else "unknown_container",
            entry_type=DeviceEntryType.SERVICE,
        )
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{self.device_name}_{entity_description.key}"

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return (
            super().available
            and self.endpoint_id in self.coordinator.data
            and self.device_name in self.coordinator.data[self.endpoint_id].containers
        )

    @property
    def container_data(self) -> PortainerContainerData:
        """Return the coordinator data for this container."""
        return self.coordinator.data[self.endpoint_id].containers[self.device_name]


class PortainerStackEntity(PortainerCoordinatorEntity):
    """Base implementation for Portainer stack."""

    def __init__(
        self,
        coordinator: PortainerCoordinator,
        entity_description: EntityDescription,
        device_info: PortainerStackData,
        via_device: PortainerCoordinatorData,
    ) -> None:
        """Initialize a Portainer stack."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._device_info = device_info
        self.stack_id = device_info.stack.id
        self.device_name = device_info.stack.name
        self.endpoint_id = via_device.endpoint.id
        self.endpoint_name = via_device.endpoint.name

        self._attr_device_info = DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    f"{coordinator.config_entry.entry_id}_{self.endpoint_id}_stack_{self.stack_id}",
                )
            },
            manufacturer=DEFAULT_NAME,
            configuration_url=URL(
                f"{coordinator.config_entry.data[CONF_URL]}#!/{self.endpoint_id}/docker/stacks/{self.device_name}"
            ),
            model="Stack",
            name=self.device_name,
            via_device=(
                DOMAIN,
                f"{coordinator.config_entry.entry_id}_{self.endpoint_id}",
            ),
        )
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{self.stack_id}_{entity_description.key}"

    @property
    def available(self) -> bool:
        """Return if the stack is available."""
        return (
            super().available
            and self.endpoint_id in self.coordinator.data
            and self.device_name in self.coordinator.data[self.endpoint_id].stacks
        )

    @property
    def stack_data(self) -> PortainerStackData:
        """Return the coordinator data for this stack."""
        return self.coordinator.data[self.endpoint_id].stacks[self.device_name]
