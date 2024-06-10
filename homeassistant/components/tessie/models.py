"""The Tessie integration models."""

from __future__ import annotations

from dataclasses import dataclass

from .coordinator import TessieStateUpdateCoordinator


@dataclass
class TessieData:
    """Data for the Tessie integration."""

    vehicles: list[TessieStateUpdateCoordinator]
