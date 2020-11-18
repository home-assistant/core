"""Xbox friends binary sensors."""
from functools import partial
from typing import Dict, List

from homeassistant.core import callback
from homeassistant.helpers.entity_registry import (
    async_get_registry as async_get_entity_registry,
)
from homeassistant.helpers.typing import HomeAssistantType

from . import GraphUpdateCoordinator
from .base_sensor import GraphBaseSensorEntity
from .const import DOMAIN

SENSOR_ATTRIBUTES = ["availability", "activity"]


async def async_setup_entry(hass: HomeAssistantType, config_entry, async_add_entities):
    """Set up Graph presence."""
    coordinator: GraphUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id][
        "coordinator"
    ]

    update_friends = partial(async_update_friends, coordinator, {}, async_add_entities)

    unsub = coordinator.async_add_listener(update_friends)
    hass.data[DOMAIN][config_entry.entry_id]["sensor_unsub"] = unsub
    update_friends()


class GraphSensorEntity(GraphBaseSensorEntity):
    """Representation of a Microsoft Graph presence state."""

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        if not self.data:
            return None

        return " ".join([part.title() for part in self.attribute.split("_")])

    @property
    def state(self):
        """Return the state of the requested attribute."""
        if not self.coordinator.last_update_success:
            return None

        return getattr(self.data, self.attribute, None)


@callback
def async_update_friends(
    coordinator: GraphUpdateCoordinator,
    current: Dict[str, List[GraphSensorEntity]],
    async_add_entities,
) -> None:
    """Update friends."""
    new_ids = set(coordinator.data.presence)
    current_ids = set(current)

    # Process new favorites, add them to Home Assistant
    new_entities = []
    for uuid in new_ids - current_ids:
        current[uuid] = [
            GraphSensorEntity(coordinator, uuid, attribute)
            for attribute in SENSOR_ATTRIBUTES
        ]
        new_entities = new_entities + current[uuid]

    if new_entities:
        async_add_entities(new_entities)

    # Process deleted favorites, remove them from Home Assistant
    for uuid in current_ids - new_ids:
        coordinator.hass.async_create_task(
            async_remove_entities(uuid, coordinator, current)
        )


async def async_remove_entities(
    uuid: str,
    coordinator: GraphUpdateCoordinator,
    current: Dict[str, GraphSensorEntity],
) -> None:
    """Remove friend sensors from Home Assistant."""
    registry = await async_get_entity_registry(coordinator.hass)
    entities = current[uuid]
    for entity in entities:
        if entity.entity_id in registry.entities:
            registry.async_remove(entity.entity_id)
    del current[uuid]
