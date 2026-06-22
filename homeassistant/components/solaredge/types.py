"""Typing for the SolarEdge Monitoring API."""

from typing import TypedDict

from aiosolaredge import SolarEdge

from homeassistant.config_entries import ConfigEntry

from .coordinator import SolarEdgeModulesCoordinator

type SolarEdgeConfigEntry = ConfigEntry[SolarEdgeData]


class SolarEdgeData(TypedDict, total=False):
    """Data for the solaredge integration."""

    api_client: SolarEdge
    modules_coordinator: SolarEdgeModulesCoordinator
