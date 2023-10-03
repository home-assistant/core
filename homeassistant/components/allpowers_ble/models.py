"""The allpowers ble integration models."""
from __future__ import annotations

from dataclasses import dataclass

from allpowers_ble import AllpowersBLE

from . import AllpowersBLECoordinator


@dataclass
class AllpowersBLEData:
    """Data for the allpowers ble integration."""

    title: str
    device: AllpowersBLE
    coordinator: AllpowersBLECoordinator
