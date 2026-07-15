"""Typing helpers for the GridX integration."""

from dataclasses import dataclass

from gridx_connector.async_connector import AsyncGridboxConnector

from homeassistant.config_entries import ConfigEntry

from .coordinator import GridxLiveCoordinator

type GridxConfigEntry = ConfigEntry[GridxData]


@dataclass
class GridxData:
    """Runtime data stored on the config entry."""

    connector: AsyncGridboxConnector
    coordinator: GridxLiveCoordinator
