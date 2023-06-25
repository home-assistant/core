"""The ld2410 ble integration models."""
from __future__ import annotations

from dataclasses import dataclass

from ld2410_ble import LD2410BLE

from .coordinator import LD2410BLECoordinator


@dataclass
class LD2410BLEData:
    """Data for the ld2410 ble integration."""

    title: str
    device: LD2410BLE
    coordinator: LD2410BLECoordinator
