"""Home Assistant KEM integration types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.config_entries import ConfigEntry

from .coordinator import KemUpdateCoordinator
from .data import HAAioKem

type KemConfigEntry = ConfigEntry[KemRuntimeData]


@dataclass
class KemRuntimeData:
    """Dataclass to hold runtime data for the KEM integration."""

    coordinators: dict[int, KemUpdateCoordinator]
    kem: HAAioKem
    homes: list[dict[str, Any]]
