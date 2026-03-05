"""Models for the Netgear integration."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .router import NetgearRouter

_LOGGER = logging.getLogger(__name__)


@dataclass
class NetgearRuntimeData:
    """Runtime data for the Netgear integration."""

    router: NetgearRouter
    coordinator_tracker: NetgearDataCoordinator[bool]
    coordinator_traffic: NetgearDataCoordinator[dict[str, Any] | None]
    coordinator_speed: NetgearDataCoordinator[dict[str, Any] | None]
    coordinator_firmware: NetgearDataCoordinator[dict[str, Any] | None]
    coordinator_utilization: NetgearDataCoordinator[dict[str, Any] | None]
    coordinator_link: NetgearDataCoordinator[dict[str, Any] | None]


type NetgearConfigEntry = ConfigEntry[NetgearRuntimeData]


class NetgearDataCoordinator[T](DataUpdateCoordinator[T]):
    """Base coordinator for Netgear."""

    config_entry: NetgearConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        router: NetgearRouter,
        entry: NetgearConfigEntry,
        *,
        name: str,
        update_interval: timedelta,
        update_method: Callable[[], Coroutine[Any, Any, T]],
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{router.device_name} {name}",
            update_interval=update_interval,
            update_method=update_method,
        )
