"""Models for use in Portainer integration."""

from dataclasses import dataclass

from .coordinator import PortainerCoordinator


@dataclass
class PortainerData:
    """Class to hold Portainer data."""

    coordinator: PortainerCoordinator
