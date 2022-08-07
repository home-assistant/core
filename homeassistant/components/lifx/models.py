"""The LIFX integration data models."""
from __future__ import annotations

from dataclasses import dataclass

from aiolifx.connection import LIFXConnection

from .coordinator import LIFXLightUpdateCoordinator, LIFXSensorUpdateCoordinator


@dataclass
class LIFXCoordination:
    """Coordination model for the lifx integration."""

    connection: LIFXConnection
    light_coordinator: LIFXLightUpdateCoordinator
    sensor_coordinator: LIFXSensorUpdateCoordinator
