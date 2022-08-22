"""The LIFX integration data models."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from aiolifx.connection import LIFXConnection

if TYPE_CHECKING:
    from .coordinator import LIFXLightUpdateCoordinator, LIFXSensorUpdateCoordinator


@dataclass
class LIFXCoordination:
    """Coordination model for the lifx integration."""

    connection: LIFXConnection
    light_coordinator: LIFXLightUpdateCoordinator
    sensor_coordinator: LIFXSensorUpdateCoordinator
