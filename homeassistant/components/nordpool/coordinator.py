"""DataUpdateCoordinator for the Nord Pool integration."""

from collections.abc import Callable
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any, override

import aiohttp
from aiozoneinfo import get_time_zone
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
            update_interval=timedelta(minutes=60),
        )
        self.client = NordPoolClient(session=async_get_clientsession(hass))
        self.listener_unsub: Callable[[], None] | None = None

    def get_next_15_interval(self, now: datetime) -> datetime:
        """Compute next time we need to notify listeners."""
        next_run = get_nordpool_current_time() + timedelta(minutes=15)
        next_minute = next_run.minute // 15 * 15
        next_run = next_run.replace(minute=next_minute, second=0, microsecond=0)

        LOGGER.debug(
            "Next listener update at %s", next_run.astimezone(NORDPOOL_TIMEZONE)
        )
        return next_run.astimezone(dt_util.UTC)

    async def update_listeners(self, now: datetime) -> None:
        """Update entity listeners every 15 minutes."""
        self.listener_unsub = async_track_point_in_utc_time(
            self.hass,
            self.update_listeners,
            self.get_next_15_interval(now),
        )
        self.async_update_listeners()

    @override
    async def _async_setup(self) -> None:
        """Set up the coordinator."""
        data = None
        tomorrow = None
        try:
            data = await self.client.async_get_delivery_periods(
                [
                    get_nordpool_current_time() - timedelta(days=1),
                    get_nordpool_current_time(),
                ],
                Currency(self.config_entry.data[CONF_CURRENCY]),
                self.config_entry.data[CONF_AREAS],
            )
            tomorrow = await self.client.async_get_delivery_periods(
                [
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
            if data:
                # Continue if we have data for today, but not tomorrow
                LOGGER.debug("Error getting prices for tomorrow: %s", error)
            else:
                LOGGER.debug("Error fetching data: %s", error)
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="no_day_data",
                ) from error

        self.data = DeliveryPeriodsData(
            raw={**data.raw, **tomorrow.raw} if tomorrow else data.raw,
            entries={**data.entries, **tomorrow.entries} if tomorrow else data.entries,
        )
        await self.update_listeners(get_nordpool_current_time())
        await super()._async_setup()

    @override
    async def _async_update_data(self) -> DeliveryPeriodsData:
        """Fetch the latest data from Nord Pool."""
        data: dict[date, DeliveryPeriodData] = {}

        today_data = self.get_data_current_day() if self.has_current_day_data else None
        tomorrow_data = self.get_data_tomorrow() if self.has_tomorrow_data else None

        if today_data and tomorrow_data:
            # Bail early if we already have all data
            return self.data

        if not today_data:
            try:
                today_data = await self._api_call(0)
            except (
                NordPoolError,
                TimeoutError,
                aiohttp.ClientError,
            ) as error:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="connection_error",
                ) from error

            if today_data and not today_data.entries:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="no_day_data",
                )

        if not tomorrow_data:
            try:
                tomorrow_data = await self._api_call(1)
            except NordPoolEmptyResponseError:
                pass
            except (
                NordPoolError,
                TimeoutError,
                aiohttp.ClientError,
            ) as error:
                LOGGER.debug("Error getting prices for tomorrow: %s", error)

        if tomorrow_data and not tomorrow_data.entries:
            tomorrow_data = None

        yesterday = (get_nordpool_current_time() - timedelta(days=1)).date()
        yesterday_raw: dict[str, Any] = self.data.raw[yesterday.isoformat()]
        yesterday_data = self.data.entries.get(
            (get_nordpool_current_time() - timedelta(days=1)).date()
        )

        if TYPE_CHECKING:
            assert today_data
            assert yesterday_data

        data[get_nordpool_current_time().date()] = today_data
        raw_data: dict[str, dict[str, Any]] = {
            today_data.raw["deliveryDateCET"]: today_data.raw
        }

        raw_data[yesterday.isoformat()] = yesterday_raw
        data[yesterday] = yesterday_data

        if tomorrow_data:
            raw_data[tomorrow_data.raw["deliveryDateCET"]] = tomorrow_data.raw
            data[(get_nordpool_current_time() + timedelta(days=1)).date()] = (
                tomorrow_data
            )

        return DeliveryPeriodsData(raw=raw_data, entries=data)

    async def _api_call(self, days: int) -> DeliveryPeriodData | None:
        """Make api call to retrieve data."""
        data: DeliveryPeriodData | None = None
        try:
            data = await self.client.async_get_delivery_period(
                get_nordpool_current_time() + timedelta(days=days),
                Currency(self.config_entry.data[CONF_CURRENCY]),
                self.config_entry.data[CONF_AREAS],
            )
        except NordPoolEmptyResponseError as error:
            LOGGER.debug("Empty response error: %s", error)
            raise
        except (
            NordPoolResponseError,
            NordPoolError,
            TimeoutError,
            aiohttp.ClientError,
        ) as error:
            LOGGER.debug("Connection error: %s", error)
            raise

        return data

    def merge_price_entries(self) -> list[DeliveryPeriodEntry]:
        """Return the merged price entries."""
        merged_entries: list[DeliveryPeriodEntry] = []
        for del_period in self.data.entries.values():
            merged_entries.extend(del_period.entries)
        return sorted(merged_entries, key=lambda x: x.start)

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
        current_day = get_nordpool_current_time().date()
        if self.data and self.data.entries:
            return current_day in self.data.entries
        return False

    @property
    def has_tomorrow_data(self) -> bool:
        """Return True if tomorrow's data is available."""
        tomorrow = get_nordpool_current_time().date() + timedelta(days=1)
        if self.data and self.data.entries:
            return tomorrow in self.data.entries
        return False
