"""Models for ESPHome Dashboard integration."""

from __future__ import annotations

from dataclasses import dataclass

from aiohttp import ClientSession

from .coordinator import ESPHomeDashboardCoordinator


@dataclass
class ESPHomeDashboardRuntimeData:
    """Runtime data for ESPHome Dashboard integration."""

    coordinator: ESPHomeDashboardCoordinator
    session: ClientSession
