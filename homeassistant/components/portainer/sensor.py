"""Sensor platform for Portainer integration."""

from collections.abc import Callable
from dataclasses import dataclass
from itertools import chain
from typing import override

from pyportainer import StackType
from pyportainer.models.docker import DockerContainerState, DockerSystemDF

from homeassistant.components.sensor import (
    EntityCategory,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    StateType,
)
from homeassistant.const import UnitOfInformation, UnitOfRatio
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import (
    PortainerConfigEntry,
    PortainerContainerData,
    PortainerStackData,
    PortainerVolumeData,
)
from .entity import (
    PortainerContainerEntity,
    PortainerCoordinatorData,
    PortainerDockerSystemDiskSpaceEndpointEntity,
    PortainerEndpointEntity,
    PortainerStackEntity,
    PortainerVolumeEntity,
)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class PortainerContainerSensorEntityDescription(SensorEntityDescription):
    """Class to hold Portainer container sensor description."""

    value_fn: Callable[[PortainerContainerData], StateType]


@dataclass(frozen=True, kw_only=True)
class PortainerEndpointSensorEntityDescription(SensorEntityDescription):
    """Class to hold Portainer endpoint sensor description."""

    value_fn: Callable[[PortainerCoordinatorData], StateType]


@dataclass(frozen=True, kw_only=True)
class PortainerStackSensorEntityDescription(SensorEntityDescription):
    """Class to hold Portainer stack sensor description."""

    value_fn: Callable[[PortainerStackData], StateType]


@dataclass(frozen=True, kw_only=True)
class PortainerDockerSystemDiskSpaceSensorEntityDescription(SensorEntityDescription):
    """Class to hold Portainer docker system disk space sensor description."""

    value_fn: Callable[[DockerSystemDF], StateType]


@dataclass(frozen=True, kw_only=True)
class PortainerVolumeSensorEntityDescription(SensorEntityDescription):
    """Class to hold Portainer volume sensor description."""

    value_fn: Callable[[PortainerVolumeData], StateType]


CONTAINER_SENSORS: tuple[PortainerContainerSensorEntityDescription, ...] = (
    PortainerContainerSensorEntityDescription(
        key="image",
        translation_key="image",
        value_fn=lambda data: data.container.image,
    ),
    PortainerContainerSensorEntityDescription(
        key="container_state",
        translation_key="container_state",
        value_fn=lambda data: data.container.state,
        device_class=SensorDeviceClass.ENUM,
        options=[state.value for state in DockerContainerState],
    ),
    PortainerContainerSensorEntityDescription(
        key="memory_limit",
        translation_key="memory_limit",
        value_fn=lambda data: (
            data.stats.memory_stats.limit if data.stats is not None else 0
        ),
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PortainerContainerSensorEntityDescription(
        key="memory_usage",
        translation_key="memory_usage",
        value_fn=lambda data: (
            data.stats.memory_stats.usage if data.stats is not None else 0
        ),
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PortainerContainerSensorEntityDescription(
        key="memory_usage_percentage",
        translation_key="memory_usage_percentage",
        value_fn=lambda data: (
            (data.stats.memory_stats.usage / data.stats.memory_stats.limit) * 100.0
            if data.stats is not None
            and data.stats.memory_stats.limit > 0
            and data.stats.memory_stats.usage > 0
            else 0.0
        ),
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PortainerContainerSensorEntityDescription(
        key="cpu_usage_total",
        translation_key="cpu_usage_total",
        value_fn=lambda data: (
            (total_delta / system_delta) * data.stats.cpu_stats.online_cpus * 100.0
            if data.stats is not None
            and (prev := data.stats_pre) is not None
            and (
                system_delta := (
                    data.stats.cpu_stats.system_cpu_usage
                    - prev.cpu_stats.system_cpu_usage
                )
            )
            > 0
            and (
                total_delta := (
                    data.stats.cpu_stats.cpu_usage.total_usage
                    - prev.cpu_stats.cpu_usage.total_usage
                )
            )
            >= 0
            and data.stats.cpu_stats.online_cpus > 0
            else 0.0
        ),
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

ENDPOINT_SENSORS: tuple[PortainerEndpointSensorEntityDescription, ...] = (
    PortainerEndpointSensorEntityDescription(
        key="api_version",
        translation_key="api_version",
        value_fn=lambda data: data.docker_version.api_version,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    PortainerEndpointSensorEntityDescription(
        key="kernel_version",
        translation_key="kernel_version",
        value_fn=lambda data: data.docker_version.kernel_version,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    PortainerEndpointSensorEntityDescription(
        key="operating_system",
        translation_key="operating_system",
        value_fn=lambda data: data.docker_info.os_type,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    PortainerEndpointSensorEntityDescription(
        key="operating_system_version",
        translation_key="operating_system_version",
        value_fn=lambda data: data.docker_info.os_version,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    PortainerEndpointSensorEntityDescription(
        key="docker_version",
        translation_key="docker_version",
        value_fn=lambda data: data.docker_info.server_version,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    PortainerEndpointSensorEntityDescription(
        key="architecture",
        translation_key="architecture",
        value_fn=lambda data: data.docker_info.architecture,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    PortainerEndpointSensorEntityDescription(
        key="containers_count",
        translation_key="containers_count",
        value_fn=lambda data: data.docker_info.containers,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PortainerEndpointSensorEntityDescription(
        key="containers_running",
        translation_key="containers_running",
        value_fn=lambda data: data.docker_info.containers_running,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PortainerEndpointSensorEntityDescription(
        key="containers_stopped",
        translation_key="containers_stopped",
        value_fn=lambda data: data.docker_info.containers_stopped,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PortainerEndpointSensorEntityDescription(
        key="containers_paused",
        translation_key="containers_paused",
        value_fn=lambda data: data.docker_info.containers_paused,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PortainerEndpointSensorEntityDescription(
        key="images_count",
        translation_key="images_count",
        value_fn=lambda data: data.docker_info.images,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PortainerEndpointSensorEntityDescription(
        key="memory_total",
        translation_key="memory_total",
        value_fn=lambda data: data.docker_info.mem_total,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.MEBIBYTES,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    PortainerEndpointSensorEntityDescription(
        key="cpu_total",
        translation_key="cpu_total",
        value_fn=lambda data: data.docker_info.ncpu,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

DOCKER_SYSTEM_DISK_SPACE_SENSORS: tuple[
    PortainerDockerSystemDiskSpaceSensorEntityDescription, ...
] = (
    PortainerDockerSystemDiskSpaceSensorEntityDescription(
        key="container_disk_usage_reclaimable",
        translation_key="container_disk_usage_reclaimable",
        value_fn=lambda data: data.container_disk_usage.reclaimable,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.MEBIBYTES,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PortainerDockerSystemDiskSpaceSensorEntityDescription(
        key="container_disk_usage_total_size",
        translation_key="container_disk_usage_total_size",
        value_fn=lambda data: data.container_disk_usage.total_size,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.MEBIBYTES,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PortainerDockerSystemDiskSpaceSensorEntityDescription(
        key="image_disk_usage_reclaimable",
        translation_key="image_disk_usage_reclaimable",
        value_fn=lambda data: data.image_disk_usage.reclaimable,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.MEBIBYTES,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PortainerDockerSystemDiskSpaceSensorEntityDescription(
        key="image_disk_usage_total_size",
        translation_key="image_disk_usage_total_size",
        value_fn=lambda data: data.image_disk_usage.total_size,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.MEBIBYTES,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PortainerDockerSystemDiskSpaceSensorEntityDescription(
        key="volume_disk_usage_total",
        translation_key="volume_disk_usage_total_size",
        value_fn=lambda data: data.volume_disk_usage.total_size,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.MEBIBYTES,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)
STACK_SENSORS: tuple[PortainerStackSensorEntityDescription, ...] = (
    PortainerStackSensorEntityDescription(
        key="stack_type",
        translation_key="stack_type",
        value_fn=lambda data: {
            stack.value: stack.name.lower() for stack in StackType
        }.get(data.stack.type),
        device_class=SensorDeviceClass.ENUM,
        options=[stack.name.lower() for stack in StackType],
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PortainerStackSensorEntityDescription(
        key="stack_containers_count",
        translation_key="stack_containers_count",
        value_fn=lambda data: data.container_count,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)
VOLUME_SENSORS: tuple[PortainerVolumeSensorEntityDescription, ...] = (
    PortainerVolumeSensorEntityDescription(
        key="volume_driver",
        translation_key="volume_driver",
        value_fn=lambda data: data.volume.driver,
    ),
    PortainerVolumeSensorEntityDescription(
        key="volume_size",
        translation_key="volume_size",
        value_fn=lambda data: (
            data.volume.usage_data.size if data.volume.usage_data else None
        ),
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PortainerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Portainer sensors based on a config entry."""
    coordinator = entry.runtime_data
    ds_coordinator = coordinator.docker_disk_space
    assert ds_coordinator is not None

    def _async_add_new_endpoints(endpoints: list[PortainerCoordinatorData]) -> None:
        """Add new endpoint sensors."""
        async_add_entities(
            chain(
                (
                    PortainerEndpointSensor(coordinator, entity_description, endpoint)
                    for entity_description in ENDPOINT_SENSORS
                    for endpoint in endpoints
                ),
                (
                    PortainerDockerSystemDiskSpaceSensor(
                        ds_coordinator,
                        entity_description,
                        endpoint,
                    )
                    for entity_description in DOCKER_SYSTEM_DISK_SPACE_SENSORS
                    for endpoint in endpoints
                ),
            )
        )

    def _async_add_new_containers(
        containers: list[tuple[PortainerCoordinatorData, PortainerContainerData]],
    ) -> None:
        """Add new container sensors."""
        async_add_entities(
            PortainerContainerSensor(
                coordinator,
                entity_description,
                container,
                endpoint,
            )
            for (endpoint, container) in containers
            for entity_description in CONTAINER_SENSORS
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

    def _async_add_new_volumes(
        volumes: list[tuple[PortainerCoordinatorData, PortainerVolumeData]],
    ) -> None:
        """Add new volume sensors."""
        async_add_entities(
            PortainerVolumeSensor(
                coordinator,
                entity_description,
                volume.volume,
                endpoint,
            )
            for (endpoint, volume) in volumes
            for entity_description in VOLUME_SENSORS
        )

    coordinator.new_endpoints_callbacks.append(_async_add_new_endpoints)
    coordinator.new_containers_callbacks.append(_async_add_new_containers)
    coordinator.new_stacks_callbacks.append(_async_add_new_stacks)
    coordinator.new_volumes_callbacks.append(_async_add_new_volumes)

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
    _async_add_new_volumes(
        [
            (endpoint, volume)
            for endpoint in coordinator.data.values()
            for volume in endpoint.volumes.values()
        ]
    )


class PortainerContainerSensor(PortainerContainerEntity, SensorEntity):
    """Representation of a Portainer container sensor."""

    entity_description: PortainerContainerSensorEntityDescription

    @property
    @override
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.container_data)


class PortainerEndpointSensor(PortainerEndpointEntity, SensorEntity):
    """Representation of a Portainer endpoint sensor."""

    entity_description: PortainerEndpointSensorEntityDescription

    @property
    @override
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        endpoint_data = self.coordinator.data[self._device_info.endpoint.id]
        return self.entity_description.value_fn(endpoint_data)


class PortainerDockerSystemDiskSpaceSensor(
    PortainerDockerSystemDiskSpaceEndpointEntity, SensorEntity
):
    """Representation of a Portainer docker system disk space sensor."""

    entity_description: PortainerDockerSystemDiskSpaceSensorEntityDescription

    @property
    @override
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        endpoint_data = self.coordinator.data[self._device_info.endpoint.id]
        return self.entity_description.value_fn(endpoint_data)


class PortainerStackSensor(PortainerStackEntity, SensorEntity):
    """Representation of a Portainer stack sensor."""

    entity_description: PortainerStackSensorEntityDescription

    @property
    @override
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.stack_data)


class PortainerVolumeSensor(PortainerVolumeEntity, SensorEntity):
    """Representation of a Portainer volume sensor."""

    entity_description: PortainerVolumeSensorEntityDescription

    @property
    @override
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.volume_data)
