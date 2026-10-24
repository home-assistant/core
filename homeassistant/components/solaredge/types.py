"""Typing for the SolarEdge Monitoring API."""

from typing import TypedDict

from homeassistant.config_entries import ConfigEntry

from .api import SolarEdgeV2
from .coordinator import SolarEdgeModulesCoordinator

type SolarEdgeConfigEntry = ConfigEntry[SolarEdgeData]


class SolarEdgeData(TypedDict, total=False):
    """Data for the solaredge integration."""

    api_client: SolarEdgeV2
    modules_coordinator: SolarEdgeModulesCoordinator
