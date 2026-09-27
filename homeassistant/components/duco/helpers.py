"""Helpers for the Duco integration."""

from homeassistant.core import callback

from .coordinator import DucoCoordinator


@callback
def async_forget_removed_node(
    coordinator: DucoCoordinator, known_nodes: set[int], node_id: int
) -> None:
    """Allow rediscovery after a node entity is removed."""
    if node_id not in coordinator.data.nodes:
        known_nodes.discard(node_id)
