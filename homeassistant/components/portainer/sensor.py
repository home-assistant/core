"""Sensor platform for Portainer integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    EntityCategory,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    StateType,
)
from homeassistant.const import PERCENTAGE, UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import (
    PortainerConfigEntry,
    PortainerContainerData,
    PortainerCoordinator,
)
from .entity import (
    PortainerContainerEntity,
    PortainerCoordinatorData,
    PortainerEndpointEntity,
)

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class PortainerContainerSensorEntityDescription(SensorEntityDescription):
    """Class to hold Portainer container sensor description."""

    value_fn: Callable[[PortainerContainerData], StateType]


@dataclass(frozen=True, kw_only=True)
class PortainerEndpointSensorEntityDescription(SensorEntityDescription):
    """Class to hold Portainer endpoint sensor description."""

    value_fn: Callable[[PortainerCoordinatorData], StateType]


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
        options=["running", "exited", "paused", "restarting", "created", "dead"],
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
        native_unit_of_measurement=PERCENTAGE,
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
        native_unit_of_measurement=PERCENTAGE,
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
    PortainerEndpointSensorEntityDescription(
        key="container_disk_usage_reclaimable",
        translation_key="container_disk_usage_reclaimable",
        value_fn=lambda data: data.docker_system_df.container_disk_usage.reclaimable,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.MEBIBYTES,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PortainerEndpointSensorEntityDescription(
        key="container_disk_usage_total_size",
        translation_key="container_disk_usage_total_size",
        value_fn=lambda data: data.docker_system_df.container_disk_usage.total_size,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.MEBIBYTES,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PortainerEndpointSensorEntityDescription(
        key="image_disk_usage_reclaimable",
        translation_key="image_disk_usage_reclaimable",
        value_fn=lambda data: data.docker_system_df.image_disk_usage.reclaimable,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.MEBIBYTES,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PortainerEndpointSensorEntityDescription(
        key="image_disk_usage_total_size",
        translation_key="image_disk_usage_total_size",
        value_fn=lambda data: data.docker_system_df.image_disk_usage.total_size,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.MEBIBYTES,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PortainerEndpointSensorEntityDescription(
        key="volume_disk_usage_total",
        translation_key="volume_disk_usage_total_size",
        value_fn=lambda data: data.docker_system_df.volume_disk_usage.total_size,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.MEBIBYTES,
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

    def _async_add_new_endpoints(endpoints: list[PortainerCoordinatorData]) -> None:
        """Add new endpoint sensor."""
        async_add_entities(
            PortainerEndpointSensor(
                coordinator,
                entity_description,
                endpoint,
            )
            for entity_description in ENDPOINT_SENSORS
            for endpoint in endpoints
            if entity_description.value_fn(endpoint)
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


class PortainerContainerSensor(PortainerContainerEntity, SensorEntity):
    """Representation of a Portainer container sensor."""

    entity_description: PortainerContainerSensorEntityDescription

    def __init__(
        self,
        coordinator: PortainerCoordinator,
        entity_description: PortainerContainerSensorEntityDescription,
        device_info: PortainerContainerData,
        via_device: PortainerCoordinatorData,
    ) -> None:
        """Initialize the Portainer container sensor."""
        self.entity_description = entity_description
        super().__init__(device_info, coordinator, via_device)

        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{self.device_name}_{entity_description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.container_data)


class PortainerEndpointSensor(PortainerEndpointEntity, SensorEntity):
    """Representation of a Portainer endpoint sensor."""

    entity_description: PortainerEndpointSensorEntityDescription

    def __init__(
        self,
        coordinator: PortainerCoordinator,
        entity_description: PortainerEndpointSensorEntityDescription,
        device_info: PortainerCoordinatorData,
    ) -> None:
        """Initialize the Portainer endpoint sensor."""
        self.entity_description = entity_description
        super().__init__(device_info, coordinator)

        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{device_info.id}_{entity_description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        endpoint_data = self.coordinator.data[self._device_info.endpoint.id]
        return self.entity_description.value_fn(endpoint_data)
