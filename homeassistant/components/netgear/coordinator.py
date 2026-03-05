"""Coordinators for the Netgear integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .router import NetgearRouter

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)
SPEED_TEST_INTERVAL = timedelta(hours=2)
SCAN_INTERVAL_FIRMWARE = timedelta(hours=5)


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


class NetgearDataCoordinator(DataUpdateCoordinator[bool]):
    """Coordinator for Netgear device tracking."""

    config_entry: NetgearConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        router: NetgearRouter,
        entry: NetgearConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{router.device_name} Devices",
            update_interval=SCAN_INTERVAL,
        )
        self.router = router

    async def _async_update_data(self) -> bool:
        """Fetch data from the router."""
        if self.router.track_devices:
            return await self.router.async_update_device_trackers()
        return False


class NetgearTrafficMeterCoordinator(DataUpdateCoordinator[dict[str, Any] | None]):
    """Coordinator for Netgear traffic meter data."""

    config_entry: NetgearConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        router: NetgearRouter,
        entry: NetgearConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{router.device_name} Traffic meter",
            update_interval=SCAN_INTERVAL,
        )
        self.router = router

    async def _async_update_data(self) -> dict[str, Any] | None:
        """Fetch data from the router."""
        return await self.router.async_get_traffic_meter()


class NetgearSpeedTestCoordinator(DataUpdateCoordinator[dict[str, Any] | None]):
    """Coordinator for Netgear speed test data."""

    config_entry: NetgearConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        router: NetgearRouter,
        entry: NetgearConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{router.device_name} Speed test",
            update_interval=SPEED_TEST_INTERVAL,
        )
        self.router = router

    async def _async_update_data(self) -> dict[str, Any] | None:
        """Fetch data from the router."""
        return await self.router.async_get_speed_test()


class NetgearFirmwareCoordinator(DataUpdateCoordinator[dict[str, Any] | None]):
    """Coordinator for Netgear firmware updates."""

    config_entry: NetgearConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        router: NetgearRouter,
        entry: NetgearConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{router.device_name} Firmware",
            update_interval=SCAN_INTERVAL_FIRMWARE,
        )
        self.router = router

    async def _async_update_data(self) -> dict[str, Any] | None:
        """Check for new firmware of the router."""
        return await self.router.async_check_new_firmware()


class NetgearUtilizationCoordinator(DataUpdateCoordinator[dict[str, Any] | None]):
    """Coordinator for Netgear utilization data."""

    config_entry: NetgearConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        router: NetgearRouter,
        entry: NetgearConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{router.device_name} Utilization",
            update_interval=SCAN_INTERVAL,
        )
        self.router = router

    async def _async_update_data(self) -> dict[str, Any] | None:
        """Fetch data from the router."""
        return await self.router.async_get_utilization()


class NetgearLinkCoordinator(DataUpdateCoordinator[dict[str, Any] | None]):
    """Coordinator for Netgear Ethernet link status."""

    config_entry: NetgearConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        router: NetgearRouter,
        entry: NetgearConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{router.device_name} Ethernet Link Status",
            update_interval=SCAN_INTERVAL,
        )
        self.router = router

    async def _async_update_data(self) -> dict[str, Any] | None:
        """Fetch data from the router."""
        return await self.router.async_get_link_status()
