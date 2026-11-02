"""Coordinator for the Sky Hub integration."""

from datetime import timedelta
import logging
from typing import override

from pyskyqhub.skyq_hub import SkyQHub

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)

type SkyHubConfigEntry = ConfigEntry[SkyHubCoordinator]


class SkyHubCoordinator(DataUpdateCoordinator[dict[str, str]]):
    """Coordinator for fetching the devices connected to a Sky Hub."""

    config_entry: SkyHubConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: SkyHubConfigEntry,
        router: SkyQHub,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.router = router

    @override
    async def _async_setup(self) -> None:
        """Connect to the router."""
        await self.router.async_connect()
        if not self.router.success_init:
            raise UpdateFailed("Unable to connect to Sky Hub")

    @override
    async def _async_update_data(self) -> dict[str, str]:
        """Fetch the connected devices."""
        data = await self.router.async_get_skyhub_data()
        if data is None:
            raise UpdateFailed("Unable to fetch devices from Sky Hub")
        return {device.mac: device.name for device in data}
