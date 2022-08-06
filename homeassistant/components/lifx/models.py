"""The LIFX integration data models."""
from __future__ import annotations

from dataclasses import dataclass

from aiolifx.connection import LIFXConnection

from .coordinator import LIFXLightUpdateCoordinator, LIFXSensorUpdateCoordinator


@dataclass
class LIFXData:
    """Data for the lifx integration."""

    connection: LIFXConnection
    coordinator_light: LIFXLightUpdateCoordinator
    coordinator_sensor: LIFXSensorUpdateCoordinator
