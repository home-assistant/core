"""Typing helpers for the GridX integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry

from .coordinator import GridxHistoricalCoordinator, GridxLiveCoordinator

if TYPE_CHECKING:
    from gridx_connector.async_connector import AsyncGridboxConnector

type GridxConfigEntry = ConfigEntry[GridxData]


@dataclass
class GridxData:
    """Runtime data stored on the config entry."""

    connector: AsyncGridboxConnector
    live_coordinator: GridxLiveCoordinator
    hist_coordinator: GridxHistoricalCoordinator
