"""Data update coordinators for AdGuard Home."""

from abc import abstractmethod
import asyncio
from dataclasses import dataclass
from datetime import timedelta
from typing import override

from adguardhome import (
    AdGuardHome,
    AdGuardHomeAuthenticationError,
    AdGuardHomeConnectionError,
    AdGuardHomeError,
    AvailableUpdate,
    FilteringConfig,
    FilterList,
    QueryLogConfig,
    SafeSearchConfig,
    Stats,
    Status,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

type AdGuardConfigEntry = ConfigEntry[AdGuardData]


@dataclass(frozen=True, kw_only=True)
class AdGuardHomeState:
    """The status of AdGuard Home and the features that can be turned on and off."""

    status: Status
    filtering: FilteringConfig
    parental: bool
    query_log: QueryLogConfig
    safe_browsing: bool
    safe_search: SafeSearchConfig


@dataclass(frozen=True, kw_only=True)
class AdGuardHomeStatistics:
    """The statistics of AdGuard Home, and its blocklists."""

    stats: Stats
    blocklists: tuple[FilterList, ...]


class AdGuardHomeCoordinator[_DataT](DataUpdateCoordinator[_DataT]):
    """Base for the coordinators of AdGuard Home."""

    config_entry: AdGuardConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: AdGuardConfigEntry,
        client: AdGuardHome,
        name: str,
        update_interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{name}",
            update_interval=update_interval,
        )
        self.client = client

    @override
    async def _async_update_data(self) -> _DataT:
        """Fetch the data from AdGuard Home."""
        try:
            return await self._async_fetch()
        except AdGuardHomeAuthenticationError as error:
            # The credentials stopped working, like after a password change in
            # AdGuard Home. This makes Home Assistant ask for new ones.
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_failed",
            ) from error
        except AdGuardHomeConnectionError as error:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from error
        except AdGuardHomeError as error:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(error)},
            ) from error

    @abstractmethod
    async def _async_fetch(self) -> _DataT:
        """Fetch the data of this coordinator from AdGuard Home."""


class AdGuardHomeStateCoordinator(AdGuardHomeCoordinator[AdGuardHomeState]):
    """Keep track of what is turned on in AdGuard Home."""

    def __init__(
        self, hass: HomeAssistant, entry: AdGuardConfigEntry, client: AdGuardHome
    ) -> None:
        """Initialize the coordinator."""
        # Often, as these back the switches, which can be changed in AdGuard Home.
        super().__init__(hass, entry, client, "state", timedelta(seconds=10))

    @override
    async def _async_fetch(self) -> AdGuardHomeState:
        """Fetch the status and settings of AdGuard Home."""
        (
            status,
            filtering,
            parental,
            query_log,
            safe_browsing,
            safe_search,
        ) = await asyncio.gather(
            self.client.status(),
            self.client.filtering.config(),
            self.client.parental.enabled(),
            self.client.querylog.config(),
            self.client.safebrowsing.enabled(),
            self.client.safesearch.config(),
        )

        return AdGuardHomeState(
            status=status,
            filtering=filtering,
            parental=parental,
            query_log=query_log,
            safe_browsing=safe_browsing,
            safe_search=safe_search,
        )


class AdGuardHomeStatisticsCoordinator(AdGuardHomeCoordinator[AdGuardHomeStatistics]):
    """Keep track of the statistics of AdGuard Home."""

    def __init__(
        self, hass: HomeAssistant, entry: AdGuardConfigEntry, client: AdGuardHome
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(hass, entry, client, "statistics", timedelta(minutes=5))

    @override
    async def _async_fetch(self) -> AdGuardHomeStatistics:
        """Fetch the statistics and blocklists of AdGuard Home."""
        stats, blocklists = await asyncio.gather(
            self.client.stats.get(),
            self.client.filtering.blocklists.list(),
        )

        return AdGuardHomeStatistics(stats=stats, blocklists=blocklists)


class AdGuardHomeUpdateCoordinator(AdGuardHomeCoordinator[AvailableUpdate]):
    """Keep track of updates for AdGuard Home."""

    def __init__(
        self, hass: HomeAssistant, entry: AdGuardConfigEntry, client: AdGuardHome
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(hass, entry, client, "update", timedelta(minutes=5))

    @override
    async def _async_fetch(self) -> AvailableUpdate:
        """Fetch the available update of AdGuard Home."""
        return await self.client.update.get()


@dataclass
class AdGuardData:
    """Data of an AdGuard Home config entry."""

    client: AdGuardHome
    state: AdGuardHomeStateCoordinator
    statistics: AdGuardHomeStatisticsCoordinator
    update: AdGuardHomeUpdateCoordinator
