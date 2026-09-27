"""Switch platform for the Duco integration."""

import logging
from typing import Any, override

from duco_connectivity import (
    ActionValueType,
    DucoError,
    DucoRateLimitError,
    KnownActionName,
    Node,
    NodeListActionItemList,
)

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import DucoConfigEntry, DucoCoordinator
from .entity import DucoEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


def _discover_identify_nodes(node_actions: NodeListActionItemList) -> set[int]:
    """Return node IDs advertising a Boolean identify action."""
    return {
        node_action.node_id
        for node_action in node_actions.nodes
        if any(
            action.action.known_value is KnownActionName.SET_IDENTIFY
            and action.val_type is ActionValueType.BOOLEAN
            for action in node_action.actions
        )
    }


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DucoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Duco switch entities."""
    coordinator = entry.runtime_data
    known_nodes: set[int] = set()

    @callback
    def _async_add_new_entities() -> None:
        """Add identify switches for newly discovered controllable nodes."""
        identify_nodes = _discover_identify_nodes(coordinator.data.node_actions)
        new_nodes = [
            node
            for node in coordinator.data.nodes.values()
            if node.node_id in identify_nodes and node.node_id not in known_nodes
        ]
        new_entities = [DucoIdentifySwitch(coordinator, node) for node in new_nodes]
        known_nodes.update(node.node_id for node in new_nodes)
        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_entities))
    _async_add_new_entities()


class DucoIdentifySwitch(DucoEntity, SwitchEntity):
    """Switch entity for a node's identify state."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "identify"

    def __init__(self, coordinator: DucoCoordinator, node: Node) -> None:
        """Initialize the switch entity."""
        super().__init__(coordinator, node)
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id}_{node.node_id}_identify"
        )

    @property
    @override
    def is_on(self) -> bool:
        """Return whether node identification is active."""
        return bool(self._node.general.identify)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on node identification."""
        await self._async_set_identify(True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off node identification."""
        await self._async_set_identify(False)

    async def _async_set_identify(self, identify: bool) -> None:
        """Set node identification."""
        try:
            await self.coordinator.async_set_node_identify(self._node_id, identify)
        except DucoRateLimitError as err:
            _LOGGER.warning("Duco write rate limit exceeded for node %s", self._node_id)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="rate_limit_exceeded",
            ) from err
        except DucoError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="failed_to_set_identify",
            ) from err
