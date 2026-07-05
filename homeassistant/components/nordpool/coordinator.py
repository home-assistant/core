"""DataUpdateCoordinator for the Nord Pool integration."""

from collections.abc import Callable
from datetime import datetime, time, timedelta
from typing import TYPE_CHECKING, override

import aiohttp
from aiozoneinfo import get_time_zone
from pynordpool import (
    Currency,
    DeliveryPeriodData,
    DeliveryPeriodEntry,
    DeliveryPeriodsData,
    NordPoolClient,
    NordPoolError,
    NordPoolResponseError,
)

from homeassistant.const import CONF_CURRENCY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import CONF_AREAS, DOMAIN, LOGGER

if TYPE_CHECKING:
    from . import NordPoolConfigEntry

NORDPOOL_TIMEZONE = get_time_zone("Europe/Oslo")


def get_nordpool_current_time() -> datetime:
    """Return the Nord Pool current time."""
    return dt_util.utcnow().astimezone(NORDPOOL_TIMEZONE)


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
        self.data_unsub: Callable[[], None] | None = None
        self.listener_unsub: Callable[[], None] | None = None

    def get_next_data_interval(self, now: datetime) -> datetime:
        """Compute next time an update should occur."""
        if self.has_current_day_data and self.has_tomorrow_data:
            _date = dt_util.now().date() + timedelta(days=1)
            _time = time(hour=0, minute=0, second=0)
            next_data_run = datetime.combine(_date, _time, NORDPOOL_TIMEZONE)
        else:
            next_data_run = dt_util.utcnow() + timedelta(hours=1)
        next_run = datetime(
            next_data_run.year,
            next_data_run.month,
            next_data_run.day,
            next_data_run.hour,
            tzinfo=dt_util.UTC,
        )
        LOGGER.debug("Next data update at %s", next_run)
        return next_run

    def get_next_15_interval(self, now: datetime) -> datetime:
        """Compute next time we need to notify listeners."""
        next_run = now + timedelta(minutes=15)
        next_minute = next_run.minute // 15 * 15
        next_run = next_run.replace(minute=next_minute, second=0, microsecond=0)

        LOGGER.debug(
            "Next listener update at %s", next_run.astimezone(NORDPOOL_TIMEZONE)
        )
        return next_run

    @override
    async def async_shutdown(self) -> None:
        """Cancel any scheduled call, and ignore new runs."""
        await super().async_shutdown()
        if self.data_unsub:
            self.data_unsub()
            self.data_unsub = None
        if self.listener_unsub:
            self.listener_unsub()
            self.listener_unsub = None

    async def update_listeners(self, now: datetime) -> None:
        """Update entity listeners."""
        self.listener_unsub = async_track_point_in_utc_time(
            self.hass,
            self.update_listeners,
            self.get_next_15_interval(now),
        )
        self.async_update_listeners()

    async def fetch_data(self, now: datetime, initial: bool = False) -> None:
        """Fetch data from Nord Pool."""
        self.data_unsub = async_track_point_in_utc_time(
            self.hass, self.fetch_data, self.get_next_data_interval(now)
        )
        if self.config_entry.pref_disable_polling and not initial:
            return
        try:
            data = await self.handle_data(initial)
        except UpdateFailed as err:
            self.async_set_update_error(err)
            return
        self.async_set_updated_data(data)
        if self.has_current_day_data and self.has_tomorrow_data:
            self.data_unsub = async_track_point_in_utc_time(
                self.hass,
                self.fetch_data,
                self.get_next_data_interval(dt_util.utcnow()),
            )

    async def handle_data(self, initial: bool = False) -> DeliveryPeriodsData:
        """Fetch data from Nord Pool."""
        data = await self.api_call()
        if data and data.entries:
            current_day = get_nordpool_current_time().date()
            if current_day in data.entries:
                LOGGER.debug("Data for current day found")
                return data

        if data and not data.entries and not initial:
            # Empty response, use cache
            LOGGER.debug("No data entries received")
            return self.data
        raise UpdateFailed(translation_domain=DOMAIN, translation_key="no_day_data")

    @override
    async def _async_update_data(self) -> DeliveryPeriodsData:
        """Fetch the latest data from the source."""
        return await self.handle_data()

    async def api_call(self, retry: int = 3) -> DeliveryPeriodsData | None:
        """Make api call to retrieve data with retry if failure."""
        data = None
        try:
            data = await self.client.async_get_delivery_periods(
                [
                    get_nordpool_current_time() - timedelta(days=1),
                    get_nordpool_current_time(),
                    get_nordpool_current_time() + timedelta(days=1),
                ],
                Currency(self.config_entry.data[CONF_CURRENCY]),
                self.config_entry.data[CONF_AREAS],
            )
        except (
            NordPoolResponseError,
            NordPoolError,
            TimeoutError,
            aiohttp.ClientError,
        ) as error:
            LOGGER.debug("Connection error: %s", error)
            if self.data is None:
                self.async_set_update_error(  # type: ignore[unreachable]
                    UpdateFailed(
                        translation_domain=DOMAIN,
                        translation_key="could_not_fetch_data",
                        translation_placeholders={"error": str(error)},
                    )
                )
            return self.data

        return data

    def merge_price_entries(self) -> list[DeliveryPeriodEntry]:
        """Return the merged price entries."""
        merged_entries: list[DeliveryPeriodEntry] = []
        for del_period in self.data.entries.values():
            merged_entries.extend(del_period.entries)
        return merged_entries

    def get_data_current_day(self) -> DeliveryPeriodData:
        """Return the current day data."""
        current_day = get_nordpool_current_time().date()
        return self.data.entries[current_day]

    def get_data_tomorrow(self) -> DeliveryPeriodData | None:
        """Return tomorrow's day data if available."""
        tomorrow = get_nordpool_current_time().date() + timedelta(days=1)
        return self.data.entries.get(tomorrow)

    @property
    def has_current_day_data(self) -> bool:
        """Return True if current day's data is available."""
        current_day = dt_util.now().date()
        if self.data and self.data.entries:
            return current_day in self.data.entries
        return False

    @property
    def has_tomorrow_data(self) -> bool:
        """Return True if tomorrow's data is available."""
        tomorrow = dt_util.now().date() + timedelta(days=1)
        if self.data and self.data.entries:
            return tomorrow in self.data.entries
        return False
