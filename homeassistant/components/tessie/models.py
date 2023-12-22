"""The Tessie integration models."""
from __future__ import annotations

from dataclasses import dataclass

from .coordinator import TessieDataUpdateCoordinator, TessieWeatherDataCoordinator


@dataclass
class TessieCoordinators:
    """Data for the Tessie integration."""

    vehicle: TessieDataUpdateCoordinator
    weather: TessieWeatherDataCoordinator
