"""The Tessie integration models."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


@dataclass
class TessieData:
    """Data for the Tessie integration."""

    coordinator: DataUpdateCoordinator
    api_key: str
