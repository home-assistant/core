"""Typing for the SolarEdge Monitoring API."""

from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from .v2_runtime import SolarEdgeV2Coordinator

from aiosolaredge import SolarEdge

from homeassistant.config_entries import ConfigEntry

from .coordinator import SolarEdgeModulesCoordinator

type SolarEdgeConfigEntry = ConfigEntry[SolarEdgeData]


class SolarEdgeData(TypedDict, total=False):
    """Data for the solaredge integration."""

    api_client: SolarEdge
    modules_coordinator: SolarEdgeModulesCoordinator
    v2_coordinator: SolarEdgeV2Coordinator
