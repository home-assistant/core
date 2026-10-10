"""Helpers for the Duco integration."""

from homeassistant.core import callback

from .const import BOX_NODE_ID
from .coordinator import DucoCoordinator


@callback
def remove_stale_node_ids(coordinator: DucoCoordinator, known_nodes: set[int]) -> None:
    """Allow rediscovery, preserving the box during incomplete node updates."""
    known_nodes.intersection_update(coordinator.data.nodes.keys() | {BOX_NODE_ID})
