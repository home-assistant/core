"""Models for the Decora BLE integration."""
from __future__ import annotations

from dataclasses import dataclass

from decora_bleak import DecoraBLEDevice


@dataclass
class DecoraBLEData:
    """Data for the DecoraBLE integration."""

    address: str
    api_key: str
    name: str
    device: DecoraBLEDevice
