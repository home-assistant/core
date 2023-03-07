"""Models for the Ooler Sleep System integration."""
from __future__ import annotations

from dataclasses import dataclass

from ooler_ble_client import OolerBLEDevice


@dataclass
class OolerData:
    """Data for the Ooler integration."""

    address: str
    model: str
    client: OolerBLEDevice
