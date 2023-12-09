"""Models for the Decora BLE integration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from decora_bleak import DecoraBLEDevice


@dataclass
class DecoraBLEData:
    """Data for the DecoraBLE integration."""

    address: str
    api_key: str
    name: str
    device: DecoraBLEDevice


@dataclass
class DiscoveredDecoraDevice:
    """Data for Decora devices discovered but not necessarily configured yet."""

    address: str
    name: str
    api_key: Optional[str]
