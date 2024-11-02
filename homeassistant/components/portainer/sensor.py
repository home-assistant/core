"""Creates the sensor entities for the node."""

from collections.abc import Callable
from dataclasses import dataclass
import logging

from aiotainer.model import Container, NodeData, State

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PortainerConfigEntry
from .coordinator import PortainerDataUpdateCoordinator
from .entity import ContainerBaseEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class ContainerSensorEntityDescription(SensorEntityDescription):
    """Describes Portainer sensor entity."""

    exists_fn: Callable[[NodeData], bool] = lambda _: True
    value_fn: Callable[[Container], str]


CONTAINER_SENSOR_TYPES: tuple[ContainerSensorEntityDescription, ...] = (
    ContainerSensorEntityDescription(
        key="container_state",
        translation_key="container_state",
        device_class=SensorDeviceClass.ENUM,
        options=[state.value for state in State],
        value_fn=lambda data: data.state.value,
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
        for container_id in (
            coordinator.data[node_id].snapshots[-1].docker_snapshot_raw.containers
        ):
            entities.extend(
                ContainerSensorEntity(coordinator, node_id, container_id, description)
                for description in CONTAINER_SENSOR_TYPES
                if description.exists_fn(coordinator.data[node_id])
            )
    async_add_entities(entities)


class ContainerSensorEntity(ContainerBaseEntity, SensorEntity):
    """Defining the Portainer Sensors with ContainerSensorEntityDescription."""

    entity_description: ContainerSensorEntityDescription

    def __init__(
        self,
        coordinator: PortainerDataUpdateCoordinator,
        node_id: int,
        container_id: str,
        description: ContainerSensorEntityDescription,
    ) -> None:
        """Set up ContainerSensors."""
        super().__init__(coordinator, node_id, container_id)
        self.entity_description = description
        self._attr_unique_id = f"{node_id}-{container_id}-{description.key}"
        self._attr_translation_placeholders = {
            "container": self.container_attributes.name
        }

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        _LOGGER.debug("Container attributes: %s", self.container_attributes)
        return self.container_attributes.state.value
