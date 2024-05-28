"""The Tessie integration models."""

from __future__ import annotations

from dataclasses import dataclass

from .coordinator import (
    TessieEnergySiteInfoCoordinator,
    TessieEnergySiteLiveCoordinator,
    TessieStateUpdateCoordinator,
)


@dataclass
class TessieData:
    """Data for the Tessie integration."""

    vehicles: list[TessieStateUpdateCoordinator]
    energy_info_coordinator: TessieEnergySiteInfoCoordinator
    energy_live_coordinator: TessieEnergySiteLiveCoordinator
