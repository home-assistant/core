"""Data update coordinators for Tasmota."""

from datetime import timedelta
import logging
from typing import override

from aiogithubapi import GitHubAPI, GitHubException, GitHubReleaseModel

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

type TasmotaConfigEntry = ConfigEntry[TasmotaLatestReleaseUpdateCoordinator]


RETRY_AFTER_UPDATE_FAILURE = timedelta(minutes=30).total_seconds()


class TasmotaLatestReleaseUpdateCoordinator(DataUpdateCoordinator[GitHubReleaseModel]):
    """Data update coordinator for Tasmota latest release info."""

    def __init__(self, hass: HomeAssistant, config_entry: TasmotaConfigEntry) -> None:
        """Initialize the coordinator."""
        self.client = GitHubAPI(session=async_get_clientsession(hass))
        super().__init__(
            hass,
            logger=logging.getLogger(__name__),
            config_entry=config_entry,
            name="Tasmota latest release",
            update_interval=timedelta(days=1),
        )

    @override
    async def _async_update_data(self) -> GitHubReleaseModel:
        """Get new data."""
        try:
            response = await self.client.repos.releases.latest("arendst/Tasmota")
        except GitHubException as ex:
            raise UpdateFailed(ex, retry_after=RETRY_AFTER_UPDATE_FAILURE) from ex
        if response.data is None:
            raise UpdateFailed(
                "No data received", retry_after=RETRY_AFTER_UPDATE_FAILURE
            )
        return response.data
