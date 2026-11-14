"""Data update coordinators for AdGuard Home."""

from abc import abstractmethod
import asyncio
from dataclasses import dataclass, replace
from datetime import timedelta
from typing import Any, override

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
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

type AdGuardConfigEntry = ConfigEntry[AdGuardData]

SWITCH_STATE_FIELDS = {
    "protection": "status",
    "filtering": "filtering",
    "parental": "parental",
    "querylog": "query_log",
    "safebrowsing": "safe_browsing",
    "safesearch": "safe_search",
}


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
        requests = {
            "status": self.client.status,
            "filtering": self.client.filtering.config,
            "parental": self.client.parental.enabled,
            "query_log": self.client.querylog.config,
            "safe_browsing": self.client.safebrowsing.enabled,
            "safe_search": self.client.safesearch.config,
        }
        # The first refresh precedes entity listeners and supplies device info
        # and diagnostics. Later refreshes retain cached data for inactive fields.
        if self.data:
            fields = {SWITCH_STATE_FIELDS[context] for context in self.async_contexts()}
            requests = {
                key: request for key, request in requests.items() if key in fields
            }

        results = await asyncio.gather(*(request() for request in requests.values()))
        data: dict[str, Any] = dict(zip(requests, results, strict=True))
        if not self.data:
            return AdGuardHomeState(**data)
        return replace(self.data, **data)


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
        self,
        hass: HomeAssistant,
        entry: AdGuardConfigEntry,
        client: AdGuardHome,
        state: AdGuardHomeStateCoordinator,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(hass, entry, client, "update", timedelta(minutes=5))
        self._state = state
        self._first_refresh = True

    @override
    async def _async_fetch(self) -> AvailableUpdate:
        """Fetch the installed version and available update of AdGuard Home."""
        if self._first_refresh:
            # Entry setup has already fetched status.
            self._first_refresh = False
        else:
            status = await self.client.status()
            # Do not reschedule switch polling or clear unrelated switch errors.
            self._state.data = replace(self._state.data, status=status)
            device_registry = dr.async_get(self.hass)
            if device := device_registry.async_get_device_by_identifier(
                (DOMAIN, self.config_entry.entry_id), self.config_entry.entry_id
            ):
                device_registry.async_update_device(
                    device.id, sw_version=str(status.version)
                )

        return await self.client.update.get()


@dataclass
class AdGuardData:
    """Data of an AdGuard Home config entry."""

    client: AdGuardHome
    state: AdGuardHomeStateCoordinator
    statistics: AdGuardHomeStatisticsCoordinator
    update: AdGuardHomeUpdateCoordinator
