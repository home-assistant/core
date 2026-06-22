"""Select platform for the Duco integration."""

import logging
from typing import override

from duco_connectivity import (
    ActionItem,
    DucoError,
    DucoRateLimitError,
    KnownActionName,
    Node,
    NodeListActionItemList,
    NodeType,
    VentilationState,
)

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import DucoConfigEntry, DucoCoordinator
from .entity import DucoEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


def _get_ventilation_options(action: ActionItem) -> tuple[str, ...] | None:
    """Return ventilation options advertised by a node action."""
    if action.action.known_value is not KnownActionName.SET_VENTILATION_STATE:
        return None

    options = tuple(str(value) for value in action.enum_values if value)
    return options or None


def _discover_ventilation_options(
    node_actions: NodeListActionItemList,
) -> dict[int, tuple[str, ...]]:
    """Build a node-to-options map from the node action metadata."""
    options_by_node: dict[int, tuple[str, ...]] = {}

    for node_action in node_actions.nodes:
        for action in node_action.actions:
            if options := _get_ventilation_options(action):
                options_by_node[node_action.node_id] = options
                break

    return options_by_node


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DucoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Duco select entities."""
    coordinator = entry.runtime_data
    known_nodes: set[int] = set()

    @callback
    def _async_add_new_entities() -> None:
        """Add select entities for newly discovered controllable nodes."""
        options_by_node = _discover_ventilation_options(coordinator.data.node_actions)
        new_entities: list[DucoVentilationStateSelect] = []

        for node in coordinator.data.nodes.values():
            if node.node_id in known_nodes:
                continue

            if node.general.node_type is not NodeType.BOX:
                continue

            options = options_by_node.get(node.node_id)
            if options is None:
                continue

            known_nodes.add(node.node_id)
            new_entities.append(DucoVentilationStateSelect(coordinator, node, options))

        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_entities))
    _async_add_new_entities()


class DucoVentilationStateSelect(DucoEntity, SelectEntity):
    """Select entity for node ventilation states."""

    _attr_translation_key = "ventilation_state"

    def __init__(
        self,
        coordinator: DucoCoordinator,
        node: Node,
        options: tuple[str, ...],
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator, node)
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id}_{node.node_id}_ventilation_state"
        )
        self._attr_options = list(options)

    @property
    @override
    def current_option(self) -> str | None:
        """Return the current ventilation state when it is selectable."""
        if (ventilation := self._node.ventilation) is None:
            return None

        if ventilation.state is VentilationState.UNKNOWN:
            return None

        state = ventilation.state.value
        if state not in self.options:
            return None

        return state

    @override
    async def async_select_option(self, option: str) -> None:
        """Set a new ventilation state on the node."""
        try:
            # SelectEntity exposes string options, and passing the raw API value
            # through keeps newly added Duco states forward-compatible.
            await self.coordinator.client.async_set_ventilation_state(
                self._node_id, option
            )
        except DucoRateLimitError as err:
            _LOGGER.warning("Duco write rate limit exceeded for node %s", self._node_id)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="rate_limit_exceeded",
            ) from err
        except DucoError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="failed_to_set_state",
            ) from err

        # Duco may normalize the requested action on readback, such as
        # MAN1x2 -> MAN1 or AUTO -> CNT1, so refresh the authoritative state.
        await self.coordinator.async_refresh()
