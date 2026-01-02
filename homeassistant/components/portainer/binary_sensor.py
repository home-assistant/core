"""Binary sensor platform for Portainer."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PortainerConfigEntry
from .const import CONTAINER_STATE_RUNNING
from .coordinator import PortainerContainerData, PortainerCoordinator
from .entity import (
    PortainerContainerEntity,
    PortainerCoordinatorData,
    PortainerEndpointEntity,
)


@dataclass(frozen=True, kw_only=True)
class PortainerContainerBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class to hold Portainer container binary sensor description."""

    state_fn: Callable[[PortainerContainerData], bool | None]


@dataclass(frozen=True, kw_only=True)
class PortainerEndpointBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class to hold Portainer endpoint binary sensor description."""

    state_fn: Callable[[PortainerCoordinatorData], bool | None]


CONTAINER_SENSORS: tuple[PortainerContainerBinarySensorEntityDescription, ...] = (
    PortainerContainerBinarySensorEntityDescription(
        key="status",
        translation_key="status",
        state_fn=lambda data: data.container.state == CONTAINER_STATE_RUNNING,
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

ENDPOINT_SENSORS: tuple[PortainerEndpointBinarySensorEntityDescription, ...] = (
    PortainerEndpointBinarySensorEntityDescription(
        key="status",
        translation_key="status",
        state_fn=lambda data: data.endpoint.status == 1,  # 1 = Running | 2 = Stopped
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PortainerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Portainer binary sensors."""
    coordinator = entry.runtime_data

    def _async_add_new_endpoints(endpoints: list[PortainerCoordinatorData]) -> None:
        """Add new endpoint binary sensors."""
        async_add_entities(
            PortainerEndpointSensor(
                coordinator,
                entity_description,
                endpoint,
            )
            for entity_description in ENDPOINT_SENSORS
            for endpoint in endpoints
            if entity_description.state_fn(endpoint)
        )

    def _async_add_new_containers(
        containers: list[tuple[PortainerCoordinatorData, PortainerContainerData]],
    ) -> None:
        """Add new container binary sensors."""
        async_add_entities(
            PortainerContainerSensor(
                coordinator,
                entity_description,
                container,
                endpoint,
            )
            for (endpoint, container) in containers
            for entity_description in CONTAINER_SENSORS
            if entity_description.state_fn(container)
        )

    coordinator.new_endpoints_callbacks.append(_async_add_new_endpoints)
    coordinator.new_containers_callbacks.append(_async_add_new_containers)

    _async_add_new_endpoints(
        [
            endpoint
            for endpoint in coordinator.data.values()
            if endpoint.id in coordinator.known_endpoints
        ]
    )
    _async_add_new_containers(
        [
            (endpoint, container)
            for endpoint in coordinator.data.values()
            for container in endpoint.containers.values()
        ]
    )


class PortainerEndpointSensor(PortainerEndpointEntity, BinarySensorEntity):
    """Representation of a Portainer endpoint binary sensor entity."""

    entity_description: PortainerEndpointBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: PortainerCoordinator,
        entity_description: PortainerEndpointBinarySensorEntityDescription,
        device_info: PortainerCoordinatorData,
    ) -> None:
        """Initialize Portainer endpoint binary sensor entity."""
        self.entity_description = entity_description
        super().__init__(device_info, coordinator)

        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{device_info.id}_{entity_description.key}"

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return super().available and self.device_id in self.coordinator.data

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.entity_description.state_fn(self.coordinator.data[self.device_id])


class PortainerContainerSensor(PortainerContainerEntity, BinarySensorEntity):
    """Representation of a Portainer container sensor."""

    entity_description: PortainerContainerBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: PortainerCoordinator,
        entity_description: PortainerContainerBinarySensorEntityDescription,
        device_info: PortainerContainerData,
        via_device: PortainerCoordinatorData,
    ) -> None:
        """Initialize the Portainer container sensor."""
        self.entity_description = entity_description
        super().__init__(device_info, coordinator, via_device)

        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{self.device_name}_{entity_description.key}"

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return super().available and self.endpoint_id in self.coordinator.data

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.entity_description.state_fn(self.container_data)
