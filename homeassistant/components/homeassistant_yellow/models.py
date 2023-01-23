"""Home Assistant Yellow data models."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


@dataclass
class YellowData:
    """Yellow data."""

    coordinator: DataUpdateCoordinator
