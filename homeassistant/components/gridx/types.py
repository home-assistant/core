"""Typing helpers for the GridX integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry

from .client import GridxConnector
from .coordinator import GridxHistoricalCoordinator, GridxLiveCoordinator

type GridxConfigEntry = ConfigEntry[GridxData]


@dataclass
class GridxData:
    """Runtime data stored on the config entry."""

    connector: GridxConnector
    live_coordinator: GridxLiveCoordinator
    hist_coordinator: GridxHistoricalCoordinator
