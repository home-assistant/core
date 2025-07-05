"""Models for the Growatt server integration."""

from dataclasses import dataclass

from .coordinator import GrowattCoordinator


@dataclass
class GrowattRuntimeData:
    """Runtime data for the Growatt integration."""

    total_coordinator: GrowattCoordinator
    devices: dict[str, GrowattCoordinator]
