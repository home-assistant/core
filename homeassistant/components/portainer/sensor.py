"""Creates the sensor entities for the node."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any

from aiotainer.model import Container, NodeData, Snapshot, State

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import PortainerConfigEntry
from .coordinator import PortainerDataUpdateCoordinator
from .entity import ContainerBaseEntity, SnapshotBaseEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class SnapshotSensorEntityDescription(SensorEntityDescription):
    """Describes Portainer sensor entity."""

    value_fn: Callable[[Snapshot], StateType | datetime]


SNAPSHOT_SENSOR_TYPES: tuple[SnapshotSensorEntityDescription, ...] = (
    SnapshotSensorEntityDescription(
        key="total_cpu",
        translation_key="total_cpu",
        suggested_display_precision=0,
        value_fn=lambda data: data.total_cpu,
    ),
    SnapshotSensorEntityDescription(
        key="total_memory",
        translation_key="total_memory",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        suggested_display_precision=2,
        value_fn=lambda data: data.total_memory,
    ),
)


@dataclass(frozen=True, kw_only=True)
class ContainerSensorEntityDescription(SensorEntityDescription):
    """Describes Portainer sensor entity."""

    exists_fn: Callable[[NodeData], bool] = lambda _: True
    extra_state_attributes_fn: Callable[[NodeData], Mapping[str, Any] | None] = (
        lambda _: None
    )
    option_fn: Callable[[NodeData], list[str] | None] = lambda _: None
    value_fn: Callable[[Container], StateType | datetime]


CONTAINER_SENSOR_TYPES: tuple[ContainerSensorEntityDescription, ...] = (
    ContainerSensorEntityDescription(
        key="container_state",
        translation_key="container_state",
        device_class=SensorDeviceClass.ENUM,
        options=list(State),
        value_fn=lambda data: data.state.name.lower(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PortainerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor platform."""
    coordinator = entry.runtime_data

    entities: list[SensorEntity] = []
    for node_id in coordinator.data:
        for snapshot in coordinator.data[node_id].snapshots:
            entities.extend(
                SnapshotSensorEntity(description, coordinator, node_id, snapshot)
                for description in SNAPSHOT_SENSOR_TYPES
            )
            for container in snapshot.docker_snapshot_raw.containers:
                entities.extend(
                    ContainerSensorEntity(
                        coordinator, node_id, snapshot, container, description
                    )
                    for description in CONTAINER_SENSOR_TYPES
                    if description.exists_fn(coordinator.data[node_id])
                )
    async_add_entities(entities)


class SnapshotSensorEntity(SnapshotBaseEntity, SensorEntity):
    """Defining the Portainer Sensors with PortainerSensorEntityDescription."""

    entity_description: ContainerSensorEntityDescription

    def __init__(
        self,
        description: SnapshotSensorEntityDescription,
        coordinator: PortainerDataUpdateCoordinator,
        node_id: int,
        snapshot: Snapshot,
    ) -> None:
        """Set up PortainerSensors."""
        super().__init__(
            coordinator,
            node_id,
            snapshot,
        )
        self.entity_description = description
        self._attr_unique_id = f"{node_id}-{description.key}"
        _LOGGER.debug("self.node_attributes %s", self.snapshot_attributes)

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        _LOGGER.debug("self.node_attributes %s", self.node_attributes)
        return self.entity_description.value_fn(self.snapshot_attributes)


class ContainerSensorEntity(ContainerBaseEntity, SensorEntity):
    """Defining the Portainer Sensors with PortainerSensorEntityDescription."""

    entity_description: ContainerSensorEntityDescription

    def __init__(
        self,
        coordinator: PortainerDataUpdateCoordinator,
        node_id: int,
        snapshot: Snapshot,
        container: Container,
        description: ContainerSensorEntityDescription,
    ) -> None:
        """Set up PortainerSensors."""
        super().__init__(coordinator, node_id, snapshot, container)
        self.entity_description = description
        _LOGGER.debug("container.names %s %s", container.names, container.id)
        self._attr_unique_id = f"{node_id}-{container.id}-{description.key}"
        # _LOGGER.debug("self.node_attributes %s", self.node_attributes)
        self.container = container
        self._attr_translation_placeholders = {"container": container.names}

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        # _LOGGER.debug("self.container_attributes %s", self.container_attributes)
        return self.entity_description.value_fn(self.container_attributes)

    @property
    def options(self) -> list[str] | None:
        """Return the option of the sensor."""
        return self.entity_description.option_fn(self.container_attributes)
