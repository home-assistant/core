"""Models for the Netgear integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .router import NetgearRouter


@dataclass
class NetgearRuntimeData:
    """Runtime data for the Netgear integration."""

    router: NetgearRouter
    coordinator: DataUpdateCoordinator[bool]
    coordinator_traffic: DataUpdateCoordinator[dict[str, Any] | None]
    coordinator_speed: DataUpdateCoordinator[dict[str, Any] | None]
    coordinator_firmware: DataUpdateCoordinator[dict[str, Any] | None]
    coordinator_utilization: DataUpdateCoordinator[dict[str, Any] | None]
    coordinator_link: DataUpdateCoordinator[dict[str, Any] | None]


type NetgearConfigEntry = ConfigEntry[NetgearRuntimeData]
