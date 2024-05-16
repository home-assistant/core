"""Coordinators for the PrusaLink integration."""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from datetime import timedelta
import logging
from time import monotonic
from typing import TypeVar

from pyprusalink import JobInfo, LegacyPrinterStatus, PrinterStatus, PrusaLink
from pyprusalink.types import InvalidAuth, PrusaLinkError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


T = TypeVar("T", PrinterStatus, LegacyPrinterStatus, JobInfo)


class PrusaLinkUpdateCoordinator(DataUpdateCoordinator[T], ABC):
    """Update coordinator for the printer."""

    config_entry: ConfigEntry
    expect_change_until = 0.0

    def __init__(self, hass: HomeAssistant, api: PrusaLink) -> None:
        """Initialize the update coordinator."""
        self.api = api

        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=self._get_update_interval(None)
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

    def _get_update_interval(self, data: T) -> timedelta:
        """Get new update interval."""
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


class JobUpdateCoordinator(PrusaLinkUpdateCoordinator[JobInfo]):
    """Job update coordinator."""

    async def _fetch_data(self) -> JobInfo:
        """Fetch the printer data."""
        return await self.api.get_job()
