"""Models for the EufyLife integration."""
from __future__ import annotations

from dataclasses import dataclass

from eufylife_ble_client import EufyLifeBLEDevice


@dataclass
class EufyLifeData:
    """Data for the EufyLife integration."""

    address: str
    model: str
    client: EufyLifeBLEDevice
