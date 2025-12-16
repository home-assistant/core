"""Collection of types used by the Electrolux integration."""

from asyncio import Task
from dataclasses import dataclass

from electrolux_group_developer_sdk.client.appliance_client import ApplianceData

from homeassistant.config_entries import ConfigEntry

from .api import ElectroluxApiClient
from .coordinator import ElectroluxDataUpdateCoordinator


@dataclass(kw_only=True, slots=True)
class ElectroluxData:
    """Electrolux data type."""

    client: ElectroluxApiClient
    coordinators: dict[str, ElectroluxDataUpdateCoordinator]
    sse_task: Task


type ElectroluxConfigEntry = ConfigEntry[ElectroluxData]


@dataclass(kw_only=True, slots=True)
class ElectroluxDiscoveryData:
    """Electrolux discovery data type."""

    discovered_appliance: ApplianceData
    entry: ElectroluxConfigEntry
