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
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

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
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensor platform."""
    coordinator = entry.runtime_data
    current_containers: dict[str, set[str]] = {}

    def _remove_containers(removed_containers, node_id) -> None:
        entity_reg = er.async_get(hass)
        for entity_entry in er.async_entries_for_config_entry(
            entity_reg, entry.entry_id
        ):
            for container_name in removed_containers:
                for description in CONTAINER_SENSOR_TYPES:
                    if entity_entry.unique_id.startswith(
                        f"{node_id}-{container_name}-{description.key}"
                    ):
                        _LOGGER.info("Deleting: %s", entity_entry.entity_id)
                        entity_reg.async_remove(entity_entry.entity_id)

    def _container_listener() -> None:
        """Listen for changes in containers and add/remove entities dynamically."""
        new_entities: list[ContainerSensorEntity] = []
        for node_id in coordinator.data:
            # Convert node_id to str if necessary, to match the expected key type in current_containers
            node_id_str = str(node_id)

            # Fetch container IDs from the latest snapshot
            container_ids = set(
                coordinator.data[node_id]
                .snapshots[-1]
                .docker_snapshot_raw.containers.keys()
            )

            # Get the current set of containers for this node, defaulting to an empty set if not present
            current_set: set[str] = current_containers.get(node_id_str, set())

            # Determine which containers were added or removed
            added_containers = container_ids - current_set
            removed_containers = current_set - container_ids

            # Add new entities for any newly detected containers
            if added_containers:
                new_entities.extend(
                    ContainerSensorEntity(
                        coordinator, node_id, container_id, description
                    )
                    for container_id in added_containers
                    for description in CONTAINER_SENSOR_TYPES
                    if description.exists_fn(coordinator.data[node_id])
                )
                current_set.update(added_containers)

            # Remove entities for containers that were removed
            if removed_containers:
                _remove_containers(removed_containers, node_id)

            # Update current containers for this node
            current_containers[node_id_str] = current_set

        # Add any newly detected entities
        if new_entities:
            async_add_entities(new_entities)

    coordinator.async_add_listener(_container_listener)
    _container_listener()


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
        # We use container name as unique id, because the container_id changes
        # with an update of the container
        self._attr_unique_id = f"{node_id}-{container_id}-{description.key}"
        self._attr_translation_placeholders = {
            "container": self.container_attributes.name
        }

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        _LOGGER.debug("Container attributes: %s", self.container_attributes)
        return self.container_attributes.state.value
