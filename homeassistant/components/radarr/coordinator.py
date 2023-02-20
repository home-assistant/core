"""Data update coordinator for the Radarr integration."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import timedelta
from typing import Generic, TypeVar, cast

from aiopyarr import Health, RadarrMovie, RootFolder, SystemStatus, exceptions
from aiopyarr.models.host_configuration import PyArrHostConfiguration
from aiopyarr.radarr_client import RadarrClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

T = TypeVar("T", bound=SystemStatus | list[RootFolder] | list[Health] | int)


class RadarrDataUpdateCoordinator(DataUpdateCoordinator[T], Generic[T], ABC):
    """Data update coordinator for the Radarr integration."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        host_configuration: PyArrHostConfiguration,
        api_client: RadarrClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )
        self.api_client = api_client
        self.host_configuration = host_configuration

    async def _async_update_data(self) -> T:
        """Get the latest data from Radarr."""
        try:
            return await self._fetch_data()

        except exceptions.ArrConnectionException as ex:
            raise UpdateFailed(ex) from ex
        except exceptions.ArrAuthenticationException as ex:
            raise ConfigEntryAuthFailed(
                "API Key is no longer valid. Please reauthenticate"
            ) from ex

    @abstractmethod
    async def _fetch_data(self) -> T:
        """Fetch the actual data."""
        raise NotImplementedError


class StatusDataUpdateCoordinator(RadarrDataUpdateCoordinator[SystemStatus]):
    """Status update coordinator for Radarr."""

    async def _fetch_data(self) -> SystemStatus:
        """Fetch the data."""
        return await self.api_client.async_get_system_status()


class DiskSpaceDataUpdateCoordinator(RadarrDataUpdateCoordinator[list[RootFolder]]):
    """Disk space update coordinator for Radarr."""

    async def _fetch_data(self) -> list[RootFolder]:
        """Fetch the data."""
        return cast(list[RootFolder], await self.api_client.async_get_root_folders())


class HealthDataUpdateCoordinator(RadarrDataUpdateCoordinator[list[Health]]):
    """Health update coordinator."""

    async def _fetch_data(self) -> list[Health]:
        """Fetch the health data."""
        return await self.api_client.async_get_failed_health_checks()


class MoviesDataUpdateCoordinator(RadarrDataUpdateCoordinator[int]):
    """Movies update coordinator."""

    async def _fetch_data(self) -> int:
        """Fetch the movies data."""
        return len(cast(list[RadarrMovie], await self.api_client.async_get_movies()))
