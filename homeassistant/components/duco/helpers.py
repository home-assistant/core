"""Helpers for the Duco integration."""

from homeassistant.core import callback

from .coordinator import DucoCoordinator


@callback
def async_remove_stale_node_ids(
    coordinator: DucoCoordinator, known_nodes: set[int]
) -> None:
    """Allow rediscovery after nodes are removed."""
    known_nodes.intersection_update(coordinator.data.nodes)
