"""Models for the Netgear integration."""

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
SCAN_INTERVAL_FIRMWARE = timedelta(hours=5)
SPEED_TEST_INTERVAL = timedelta(hours=2)


@dataclass
class NetgearRuntimeData:
    """Runtime data for the Netgear integration."""

    router: NetgearRouter
    coordinator_tracker: NetgearTrackerCoordinator
    coordinator_traffic: NetgearTrafficMeterCoordinator
    coordinator_speed: NetgearSpeedTestCoordinator
    coordinator_firmware: NetgearFirmwareCoordinator
    coordinator_utilization: NetgearUtilizationCoordinator
    coordinator_link: NetgearLinkCoordinator


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
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{router.device_name} {name}",
            update_interval=update_interval,
        )
        self.router = router


class NetgearTrackerCoordinator(NetgearDataCoordinator[bool]):
    """Coordinator for Netgear device tracking."""

    def __init__(
        self, hass: HomeAssistant, router: NetgearRouter, entry: NetgearConfigEntry
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass, router, entry, name="Devices", update_interval=SCAN_INTERVAL
        )

    async def _async_update_data(self) -> bool:
        """Fetch data from the router."""
        if self.router.track_devices:
            return await self.router.async_update_device_trackers()
        return False


class NetgearTrafficMeterCoordinator(NetgearDataCoordinator[dict[str, Any] | None]):
    """Coordinator for Netgear traffic meter data."""

    def __init__(
        self, hass: HomeAssistant, router: NetgearRouter, entry: NetgearConfigEntry
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass, router, entry, name="Traffic meter", update_interval=SCAN_INTERVAL
        )

    async def _async_update_data(self) -> dict[str, Any] | None:
        """Fetch data from the router."""
        return await self.router.async_get_traffic_meter()


class NetgearSpeedTestCoordinator(NetgearDataCoordinator[dict[str, Any] | None]):
    """Coordinator for Netgear speed test data."""

    def __init__(
        self, hass: HomeAssistant, router: NetgearRouter, entry: NetgearConfigEntry
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass, router, entry, name="Speed test", update_interval=SPEED_TEST_INTERVAL
        )

    async def _async_update_data(self) -> dict[str, Any] | None:
        """Fetch data from the router."""
        return await self.router.async_get_speed_test()


class NetgearFirmwareCoordinator(NetgearDataCoordinator[dict[str, Any] | None]):
    """Coordinator for Netgear firmware updates."""

    def __init__(
        self, hass: HomeAssistant, router: NetgearRouter, entry: NetgearConfigEntry
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass, router, entry, name="Firmware", update_interval=SCAN_INTERVAL_FIRMWARE
        )

    async def _async_update_data(self) -> dict[str, Any] | None:
        """Check for new firmware of the router."""
        return await self.router.async_check_new_firmware()


class NetgearUtilizationCoordinator(NetgearDataCoordinator[dict[str, Any] | None]):
    """Coordinator for Netgear utilization data."""

    def __init__(
        self, hass: HomeAssistant, router: NetgearRouter, entry: NetgearConfigEntry
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass, router, entry, name="Utilization", update_interval=SCAN_INTERVAL
        )

    async def _async_update_data(self) -> dict[str, Any] | None:
        """Fetch data from the router."""
        return await self.router.async_get_utilization()


class NetgearLinkCoordinator(NetgearDataCoordinator[dict[str, Any] | None]):
    """Coordinator for Netgear Ethernet link status."""

    def __init__(
        self, hass: HomeAssistant, router: NetgearRouter, entry: NetgearConfigEntry
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            router,
            entry,
            name="Ethernet Link Status",
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, Any] | None:
        """Fetch data from the router."""
        return await self.router.async_get_link_status()
