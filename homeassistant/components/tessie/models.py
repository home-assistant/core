"""The Tessie integration models."""
from __future__ import annotations

from dataclasses import dataclass

from .coordinator import TessieDataUpdateCoordinator, TessieWeatherDataCoordinator


@dataclass
class TessieVehicle:
    """Data for the Tessie integration."""

    state_coordinator: TessieDataUpdateCoordinator
    weather_coordinator: TessieWeatherDataCoordinator
