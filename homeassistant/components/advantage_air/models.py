"""The Advantage Air integration models."""
from __future__ import annotations

from dataclasses import dataclass

from advantage_air import advantage_air

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


@dataclass
class AdvantageAirData:
    """Data for the Advantage Air integration."""

    coordinator: DataUpdateCoordinator
    api: advantage_air
