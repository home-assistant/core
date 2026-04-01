"""Typing helpers for the GridX integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.config_entries import ConfigEntry

from .coordinator import GridxHistoricalCoordinator, GridxLiveCoordinator

type GridxConfigEntry = ConfigEntry[GridxData]


@dataclass
class GridxData:
    """Runtime data stored on the config entry."""

    connector: Any
    live_coordinator: GridxLiveCoordinator
    hist_coordinator: GridxHistoricalCoordinator
