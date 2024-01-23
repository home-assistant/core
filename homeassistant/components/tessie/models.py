"""The Tessie integration models."""
from __future__ import annotations

from dataclasses import dataclass

from .coordinator import TessieStateUpdateCoordinator


@dataclass
class TessieVehicle:
    """Data for the Tessie integration."""

    state_coordinator: TessieStateUpdateCoordinator
