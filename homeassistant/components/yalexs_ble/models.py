"""The yalexs_ble integration models."""
from __future__ import annotations

from dataclasses import dataclass

from yalexs_ble import PushLock


@dataclass
class YaleXSBLEData:
    """Data for the yale xs ble integration."""

    title: str
    lock: PushLock
    always_connected: bool
