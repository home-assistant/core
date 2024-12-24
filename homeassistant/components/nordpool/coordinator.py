"""DataUpdateCoordinator for the Nord Pool integration."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from pynordpool import (
    Currency,
    DeliveryPeriodData,
    DeliveryPeriodEntry,
    DeliveryPeriodsData,
    NordPoolClient,
    NordPoolEmptyResponseError,
    NordPoolError,
    NordPoolResponseError,
)

from homeassistant.const import CONF_CURRENCY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import CONF_AREAS, DOMAIN, LOGGER

if TYPE_CHECKING:
    from . import NordPoolConfigEntry


class NordPoolDataUpdateCoordinator(DataUpdateCoordinator[DeliveryPeriodsData]):
    """A Nord Pool Data Update Coordinator."""

    config_entry: NordPoolConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: NordPoolConfigEntry) -> None:
        """Initialize the Nord Pool coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
        )
        self.client = NordPoolClient(session=async_get_clientsession(hass))
        self.unsub: Callable[[], None] | None = None

    def get_next_interval(self, now: datetime) -> datetime:
        """Compute next time an update should occur."""
        next_hour = dt_util.utcnow() + timedelta(hours=1)
        next_run = datetime(
            next_hour.year,
            next_hour.month,
            next_hour.day,
            next_hour.hour,
            tzinfo=dt_util.UTC,
        )
        LOGGER.debug("Next update at %s", next_run)
        return next_run

    async def async_shutdown(self) -> None:
        """Cancel any scheduled call, and ignore new runs."""
        await super().async_shutdown()
        if self.unsub:
            self.unsub()
            self.unsub = None

    async def fetch_data(self, now: datetime) -> None:
        """Fetch data from Nord Pool."""
        self.unsub = async_track_point_in_utc_time(
            self.hass, self.fetch_data, self.get_next_interval(dt_util.utcnow())
        )
        data = await self.api_call()
        if data:
            self.async_set_updated_data(data)

    async def api_call(self, retry: int = 3) -> DeliveryPeriodsData | None:
        """Make api call to retrieve data with retry if failure."""
        data = None
        try:
            data = await self.client.async_get_delivery_periods(
                [
                    dt_util.now() - timedelta(days=1),
                    dt_util.now(),
                    dt_util.now() + timedelta(days=1),
                ],
                Currency(self.config_entry.data[CONF_CURRENCY]),
                self.config_entry.data[CONF_AREAS],
            )
        except (
            NordPoolEmptyResponseError,
            NordPoolResponseError,
            NordPoolError,
        ) as error:
            LOGGER.debug("Connection error: %s", error)
            if retry > 0:
                next_run = (4 - retry) * 15
                LOGGER.debug("Wait %d seconds for next try", next_run)
                await asyncio.sleep(next_run)
                return await self.api_call(retry - 1)
            self.async_set_update_error(error)

        return data

    def merge_price_entries(self) -> list[DeliveryPeriodEntry]:
        """Return the merged price entries."""
        merged_entries: list[DeliveryPeriodEntry] = []
        for del_period in self.data.entries:
            merged_entries.extend(del_period.entries)
        return merged_entries

    def get_data_current_day(self) -> DeliveryPeriodData:
        """Return the current day data."""
        current_day = dt_util.utcnow().strftime("%Y-%m-%d")
        delivery_period: DeliveryPeriodData = self.data.entries[0]
        for del_period in self.data.entries:
            if del_period.requested_date == current_day:
                delivery_period = del_period
                break
        return delivery_period
