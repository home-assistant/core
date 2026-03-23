"""Base class for Portainer entities."""

import logging

from yarl import URL

from homeassistant.const import CONF_URL
from homeassistant.core import callback
import homeassistant.helpers.device_registry as dr
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

_LOGGER = logging.getLogger(__name__)


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

        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{self.device_name}_{entity_description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info, always reflecting the current container ID."""
        container_id = (
            self.container_data.container.id if self.available else self.device_id
        )
        return DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    f"{self.coordinator.config_entry.entry_id}_{self.endpoint_id}_{self.device_name}",
                )
            },
            manufacturer=DEFAULT_NAME,
            configuration_url=URL(
                f"{self.coordinator.config_entry.data[CONF_URL]}"
                f"#!/{self.endpoint_id}/docker/containers/{container_id}"
            ),
            model="Container",
            name=self.device_name,
            via_device=(
                DOMAIN,
                f"{self.coordinator.config_entry.entry_id}_{self.endpoint_id}_stack_{self._device_info.stack.id}"
                if self._device_info.stack
                else f"{self.coordinator.config_entry.entry_id}_{self.endpoint_id}",
            ),
            translation_key=None if self.device_name else "unknown_container",
            entry_type=DeviceEntryType.SERVICE,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator, keeping URL current."""
        if self.available and self.device_entry:
            new_configuration_url = URL(
                f"{self.coordinator.config_entry.data[CONF_URL]}"
                f"#!/{self.endpoint_id}/docker/containers/{self.container_data.container.id}"
            )

            if self.device_entry.configuration_url != new_configuration_url:
                _LOGGER.debug(
                    "Updating configuration URL for device %s: %s -> %s",
                    self.device_entry.id,
                    self.device_entry.configuration_url,
                    new_configuration_url,
                )
                dr.async_get(self.hass).async_update_device(
                    device_id=self.device_entry.id,
                    configuration_url=new_configuration_url,
                )
        super()._handle_coordinator_update()

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
