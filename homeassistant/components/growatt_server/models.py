"""Models for the Growatt server integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .coordinator import GrowattCoordinator


@dataclass
class GrowattRuntimeData:
    """Runtime data for the Growatt integration."""

    total_coordinator: GrowattCoordinator
    devices: dict[str, GrowattCoordinator]
