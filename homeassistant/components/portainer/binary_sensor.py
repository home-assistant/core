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
from .const import ContainerState, EndpointStatus, StackStatus
from .coordinator import PortainerContainerData
from .entity import (
    PortainerContainerEntity,
    PortainerCoordinatorData,
    PortainerEndpointEntity,
    PortainerStackData,
    PortainerStackEntity,
)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class PortainerContainerBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class to hold Portainer container binary sensor description."""

    state_fn: Callable[[PortainerContainerData], bool | None]


@dataclass(frozen=True, kw_only=True)
class PortainerEndpointBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class to hold Portainer endpoint binary sensor description."""

    state_fn: Callable[[PortainerCoordinatorData], bool | None]


@dataclass(frozen=True, kw_only=True)
class PortainerStackBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class to hold Portainer stack binary sensor description."""

    state_fn: Callable[[PortainerStackData], bool | None]


CONTAINER_SENSORS: tuple[PortainerContainerBinarySensorEntityDescription, ...] = (
    PortainerContainerBinarySensorEntityDescription(
        key="status",
        translation_key="status",
        state_fn=lambda data: data.container.state == ContainerState.RUNNING,
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

ENDPOINT_SENSORS: tuple[PortainerEndpointBinarySensorEntityDescription, ...] = (
    PortainerEndpointBinarySensorEntityDescription(
        key="status",
        translation_key="status",
        state_fn=lambda data: data.endpoint.status == EndpointStatus.UP,
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

STACK_SENSORS: tuple[PortainerStackBinarySensorEntityDescription, ...] = (
    PortainerStackBinarySensorEntityDescription(
        key="stack_status",
        translation_key="status",
        state_fn=lambda data: data.stack.status == StackStatus.ACTIVE,
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

    def _async_add_new_stacks(
        stacks: list[tuple[PortainerCoordinatorData, PortainerStackData]],
    ) -> None:
        """Add new stack sensors."""
        async_add_entities(
            PortainerStackSensor(
                coordinator,
                entity_description,
                stack,
                endpoint,
            )
            for (endpoint, stack) in stacks
            for entity_description in STACK_SENSORS
        )

    coordinator.new_endpoints_callbacks.append(_async_add_new_endpoints)
    coordinator.new_containers_callbacks.append(_async_add_new_containers)
    coordinator.new_stacks_callbacks.append(_async_add_new_stacks)
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
    _async_add_new_stacks(
        [
            (endpoint, stack)
            for endpoint in coordinator.data.values()
            for stack in endpoint.stacks.values()
        ]
    )


class PortainerEndpointSensor(PortainerEndpointEntity, BinarySensorEntity):
    """Representation of a Portainer endpoint binary sensor entity."""

    entity_description: PortainerEndpointBinarySensorEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.entity_description.state_fn(self.coordinator.data[self.device_id])


class PortainerContainerSensor(PortainerContainerEntity, BinarySensorEntity):
    """Representation of a Portainer container sensor."""

    entity_description: PortainerContainerBinarySensorEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.entity_description.state_fn(self.container_data)


class PortainerStackSensor(PortainerStackEntity, BinarySensorEntity):
    """Representation of a Portainer stack sensor."""

    entity_description: PortainerStackBinarySensorEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.entity_description.state_fn(self.stack_data)
