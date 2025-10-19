"""Sensor platform for Portainer integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pyportainer.models.docker import DockerContainer

from homeassistant.components.sensor import (
    EntityCategory,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    StateType,
)
from homeassistant.const import UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PortainerConfigEntry, PortainerCoordinator
from .entity import (
    PortainerContainerEntity,
    PortainerCoordinatorData,
    PortainerEndpointEntity,
)


@dataclass(frozen=True, kw_only=True)
class PortainerContainerSensorEntityDescription(SensorEntityDescription):
    """Class to hold Portainer container sensor description."""

    value_fn: Callable[[DockerContainer], StateType]


@dataclass(frozen=True, kw_only=True)
class PortainerEndpointSensorEntityDescription(SensorEntityDescription):
    """Class to hold Portainer endpoint sensor description."""

    value_fn: Callable[[PortainerCoordinatorData], StateType]


CONTAINER_SENSORS: tuple[PortainerContainerSensorEntityDescription, ...] = (
    PortainerContainerSensorEntityDescription(
        key="image",
        translation_key="image",
        value_fn=lambda data: data.image,
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
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PortainerEndpointSensorEntityDescription(
        key="containers_running",
        translation_key="containers_running",
        value_fn=lambda data: data.docker_info.containers_running,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PortainerEndpointSensorEntityDescription(
        key="containers_stopped",
        translation_key="containers_stopped",
        value_fn=lambda data: data.docker_info.containers_stopped,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PortainerEndpointSensorEntityDescription(
        key="containers_paused",
        translation_key="containers_paused",
        value_fn=lambda data: data.docker_info.containers_paused,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PortainerEndpointSensorEntityDescription(
        key="images_count",
        translation_key="images_count",
        value_fn=lambda data: data.docker_info.images,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PortainerEndpointSensorEntityDescription(
        key="memory_total",
        translation_key="memory_total",
        value_fn=lambda data: data.docker_info.mem_total,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfInformation.BYTES,
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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PortainerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Portainer sensors based on a config entry."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = []

    for endpoint in coordinator.data.values():
        entities.extend(
            PortainerEndpointSensor(
                coordinator,
                entity_description,
                endpoint,
            )
            for entity_description in ENDPOINT_SENSORS
        )

        entities.extend(
            PortainerContainerSensor(
                coordinator,
                entity_description,
                container,
                endpoint,
            )
            for container in endpoint.containers.values()
            for entity_description in CONTAINER_SENSORS
        )

    async_add_entities(entities)


class PortainerContainerSensor(PortainerContainerEntity, SensorEntity):
    """Representation of a Portainer container sensor."""

    entity_description: PortainerContainerSensorEntityDescription

    def __init__(
        self,
        coordinator: PortainerCoordinator,
        entity_description: PortainerContainerSensorEntityDescription,
        device_info: DockerContainer,
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
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(
            self.coordinator.data[self.endpoint_id].containers[self.device_id]
        )


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
    def available(self) -> bool:
        """Return if the device is available."""
        return super().available and self.device_id in self.coordinator.data

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        endpoint_data = self.coordinator.data[self._device_info.endpoint.id]
        return self.entity_description.value_fn(endpoint_data)
