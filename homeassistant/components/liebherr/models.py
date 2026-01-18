"""Data models for Liebherr integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry

from .coordinator import LiebherrCoordinator

type LiebherrConfigEntry = ConfigEntry[LiebherrData]


@dataclass
class LiebherrData:
    """Liebherr data stored in runtime_data."""

    coordinator: LiebherrCoordinator
