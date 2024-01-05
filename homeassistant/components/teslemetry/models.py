"""The Teslemetry integration models."""
from __future__ import annotations

from dataclasses import dataclass

from .coordinator import TeslemetryStateUpdateCoordinator


@dataclass
class TeslemetryVehicle:
    """Data for the Teslemetry integration."""

    state_coordinator: TeslemetryStateUpdateCoordinator
