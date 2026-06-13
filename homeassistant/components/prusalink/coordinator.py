"""Coordinators for the PrusaLink integration."""

from abc import ABC, abstractmethod
import asyncio
from datetime import timedelta
import logging
from time import monotonic
from typing import TypeVar

from httpx import ConnectError
from pyprusalink import (
    JobInfo,
    LegacyPrinterStatus,
    PrinterInfo,
    PrinterStatus,
    PrusaLink,
    VersionInfo,
)
from pyprusalink.types import InvalidAuth, PrusaLinkError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Allow automations using homeassistant.update_entity to collect
# rapidly-changing metrics.
_MINIMUM_REFRESH_INTERVAL = 1.0

# Job is the only coordinator whose payload can be None — pyprusalink's
# get_job() returns None on HTTP 204 when no job is running. The other
# endpoints always return data or raise on failure. Using `bound=` rather
# than constraint members so `JobInfo | None` fits without forcing a union
# into the constraint list.
T = TypeVar(
    "T",
    bound=PrinterStatus
    | LegacyPrinterStatus
    | JobInfo
    | None
    | PrinterInfo
    | VersionInfo,
)


type PrusaLinkConfigEntry = ConfigEntry[dict[str, PrusaLinkUpdateCoordinator]]


class PrusaLinkUpdateCoordinator(DataUpdateCoordinator[T], ABC):
    """Update coordinator for the printer."""

    config_entry: PrusaLinkConfigEntry
    expect_change_until = 0.0

    def __init__(
        self, hass: HomeAssistant, config_entry: PrusaLinkConfigEntry, api: PrusaLink
    ) -> None:
        """Initialize the update coordinator."""
        self.api = api

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=self._get_update_interval(None),
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=_MINIMUM_REFRESH_INTERVAL, immediate=True
            ),
        )

    async def _async_update_data(self) -> T:
        """Update the data."""
        try:
            async with asyncio.timeout(5):
                data = await self._fetch_data()
        except InvalidAuth:
            raise UpdateFailed("Invalid authentication") from None
        except PrusaLinkError as err:
            raise UpdateFailed(str(err)) from err
        except (TimeoutError, ConnectError) as err:
            raise UpdateFailed("Cannot connect") from err

        self.update_interval = self._get_update_interval(data)
        return data

    @abstractmethod
    async def _fetch_data(self) -> T:
        """Fetch the actual data."""
        raise NotImplementedError

    @callback
    def expect_change(self) -> None:
        """Expect a change."""
        self.expect_change_until = monotonic() + 30

    def _get_update_interval(self, data: T | None) -> timedelta:
        """Get new update interval.

        `data` is unused by the base implementation today, but kept on the
        signature so subclasses can override based on payload state — e.g. a
        future transfer coordinator that polls faster while a transfer is
        active. The base class is called once from `__init__` with `None`
        before the first fetch, hence `T | None`.
        """
        if self.expect_change_until > monotonic():
            return timedelta(seconds=5)

        return timedelta(seconds=30)


class StatusCoordinator(PrusaLinkUpdateCoordinator[PrinterStatus]):
    """Printer update coordinator."""

    async def _fetch_data(self) -> PrinterStatus:
        """Fetch the printer data."""
        return await self.api.get_status()


class LegacyStatusCoordinator(PrusaLinkUpdateCoordinator[LegacyPrinterStatus]):
    """Printer legacy update coordinator."""

    async def _fetch_data(self) -> LegacyPrinterStatus:
        """Fetch the printer data."""
        return await self.api.get_legacy_printer()


class JobUpdateCoordinator(PrusaLinkUpdateCoordinator[JobInfo | None]):
    """Job update coordinator.

    The job endpoint returns nothing (HTTP 204) when no job is running, so
    `data` can legitimately be `None` here. Entity code that reads from this
    coordinator's data must be `None`-aware.
    """

    async def _fetch_data(self) -> JobInfo | None:
        """Fetch the printer data."""
        return await self.api.get_job()


class InfoUpdateCoordinator(PrusaLinkUpdateCoordinator[PrinterInfo]):
    """Info update coordinator."""

    async def _fetch_data(self) -> PrinterInfo:
        """Fetch the printer data."""
        return await self.api.get_info()


class VersionUpdateCoordinator(PrusaLinkUpdateCoordinator[VersionInfo]):
    """Version update coordinator."""

    async def _fetch_data(self) -> VersionInfo:
        """Fetch the version data."""
        return await self.api.get_version()
