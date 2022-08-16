"""SRP Energy Coordinator."""
from __future__ import annotations

# import datetime as dt
from datetime import datetime, timedelta
import logging
from typing import TypedDict

import async_timeout
from srpenergy.client import SrpEnergyClient

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    DAILY_KEY_DATE_FORMAT,
    DATA_SUMMARY_KEY_DATE,
    DATA_SUMMARY_KEY_DAY,
    DATA_SUMMARY_KEY_HOUR,
    DATA_SUMMARY_KEY_VALUE,
    DOMAIN,
    HOURLY_KEY_DATE_FORMAT,
    PHOENIX_TIME_ZONE,
    TIME_DELTA_BETWEEN_API_UPDATES,
    TIME_DELTA_BETWEEN_UPDATES,
)

_LOGGER = logging.getLogger(__name__)


class SrpAggregateData(TypedDict):
    """Class for defining Aggregate data in dict."""

    day: str
    hour: str
    iso_date: str
    value: float


class SrpEnergyData(TypedDict):
    """Class for defining data in dict."""

    energy_usage_this_day: float
    energy_usage_price_this_day: float
    energy_usage_this_month: float
    energy_usage_price_this_month: float
    energy_usage_this_day_1_day_ago: float
    energy_usage_price_this_day_1_day_ago: float
    energy_usage_this_month_1_day_ago: float
    energy_usage_price_this_month_1_day_ago: float
    hourly_energy_usage_past_48hr: dict[str, SrpAggregateData]
    hourly_energy_usage_price_past_48hr: dict[str, SrpAggregateData]
    daily_energy_usage_past_2weeks: dict[str, SrpAggregateData]
    daily_energy_usage_price_past_2weeks: dict[str, SrpAggregateData]


class SrpApiCoordinator(DataUpdateCoordinator):
    """Srp api data coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: SrpEnergyClient,
        name: str,
        is_time_of_use: bool = False,
    ) -> None:
        """Initialize my coordinator."""
        _LOGGER.debug("API:DataCoordinator: Init")
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name=DOMAIN,
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=TIME_DELTA_BETWEEN_API_UPDATES,
        )
        self.api = api
        self.name = name
        self.is_time_of_use = is_time_of_use

    async def async_get_api_data(
        self,
    ) -> tuple[list[tuple[str, str, str, str, str]], tuple[datetime, datetime]]:
        """Fetch data from API endpoint."""
        try:
            _LOGGER.debug("API:DataCoordinator: async_get_api_data enter")

            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with async_timeout.timeout(10):
                end_date = dt_util.now(PHOENIX_TIME_ZONE)
                start_date = end_date - timedelta(days=45)
                hourly_usage = await self.hass.async_add_executor_job(
                    self.api.usage,
                    start_date,
                    end_date,
                    self.is_time_of_use,
                )

                _LOGGER.debug(
                    "API:DataCoordinator: async_get_api_data: Received %s records from %s to %s",
                    len(hourly_usage) if hourly_usage else "None",
                    start_date,
                    end_date,
                )

                return hourly_usage, (start_date, end_date)

        except ValueError as err:
            raise UpdateFailed("Error updating. Check date range.") from err
        except Exception as err:
            raise UpdateFailed("Error communicating with API.") from err

    async def _async_update_data(
        self,
    ) -> tuple[list[tuple[str, str, str, str, str]], tuple[datetime, datetime]]:
        """Fetch data from API endpoint."""
        _LOGGER.debug(
            "API:DataCoordinator: _async_update_data: request to refresh data"
        )

        result = await self.async_get_api_data()

        return result


class SrpCoordinator(DataUpdateCoordinator):
    """Srp data coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: SrpEnergyClient,
        api_coordiator: SrpApiCoordinator,
        name: str,
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name=DOMAIN,
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=TIME_DELTA_BETWEEN_UPDATES,
        )
        _LOGGER.debug("SrpDataCoordinator: Init")
        self.api = api
        self.api_coordinator = api_coordiator
        self.api_coordinator.async_add_listener(self._handle_api_coordinator_update)
        self.name = name
        self.search_date_range: tuple[datetime, datetime] | None = None
        self.min_date: datetime | None = None
        self.max_date: datetime | None = None
        self.hourly_usage: list[tuple[str, str, str, str, str]] | None = None

    def _handle_api_coordinator_update(self) -> None:
        """Handle updated data from the api coordinator."""
        # New data from api data coordinator
        self.hourly_usage, self.search_date_range = self.api_coordinator.data
        _LOGGER.debug(
            "SrpDataCoordinator: _handle_api_coordinator_update: %s new records from API search range %s",
            len(self.hourly_usage) if self.hourly_usage else "None",
            self.search_date_range,
        )

    async def _async_update_data(self) -> SrpEnergyData:
        """Fetch data from API endpoint."""
        _LOGGER.debug("SrpDataCoordinator: _async_update_data: request to refresh data")

        result: SrpEnergyData = {
            "energy_usage_this_day": 0.0,
            "energy_usage_price_this_day": 0.0,
            "energy_usage_this_month": 0.0,
            "energy_usage_price_this_month": 0.0,
            "energy_usage_this_day_1_day_ago": 0.0,
            "energy_usage_price_this_day_1_day_ago": 0.0,
            "energy_usage_this_month_1_day_ago": 0.0,
            "energy_usage_price_this_month_1_day_ago": 0.0,
            "hourly_energy_usage_past_48hr": {},
            "hourly_energy_usage_price_past_48hr": {},
            "daily_energy_usage_past_2weeks": {},
            "daily_energy_usage_price_past_2weeks": {},
        }

        if self.hourly_usage:

            time_zone = dt_util.get_time_zone(self.hass.config.time_zone)
            datetime_now = dt_util.now(time_zone)
            datetime_now_start = datetime_now.replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            yesterday = datetime_now - timedelta(days=1)
            yesterday_start = yesterday.replace(
                hour=0, minute=0, second=0, microsecond=0
            )

            _LOGGER.debug(
                "SrpDataCoordinator: _async_update_data: datetime_now: %s; datetime_now_start: %s; yesterday: %s; yesterday_start: %s;",
                datetime_now,
                datetime_now_start,
                yesterday,
                yesterday_start,
            )

            # calculate totals
            energy_usage_this_day = 0.0
            energy_usage_price_this_day = 0.0
            energy_usage_this_month = 0.0
            energy_usage_price_this_month = 0.0
            energy_usage_this_day_1_day_ago = 0.0
            energy_usage_price_this_day_1_day_ago = 0.0
            energy_usage_this_month_1_day_ago = 0.0
            energy_usage_price_this_month_1_day_ago = 0.0
            hourly_energy_usage_past_48hr: dict[str, SrpAggregateData] = {}
            hourly_energy_usage_price_past_48hr: dict[str, SrpAggregateData] = {}
            daily_energy_usage_past_2weeks: dict[str, SrpAggregateData] = {}
            daily_energy_usage_price_past_2weeks: dict[str, SrpAggregateData] = {}

            for day, hour, iso_date, kwh, cost in self.hourly_usage:
                cur_datetime = datetime.fromisoformat(iso_date)
                cur_datetime = cur_datetime.replace(tzinfo=PHOENIX_TIME_ZONE)

                if not self.min_date:
                    self.min_date = cur_datetime
                if not self.max_date:
                    self.max_date = cur_datetime
                self.min_date = min(self.min_date, cur_datetime)
                self.max_date = max(self.max_date, cur_datetime)

                # Energy Usage this Day
                if datetime_now_start <= cur_datetime <= datetime_now:
                    energy_usage_this_day += float(kwh)
                    energy_usage_price_this_day += float(cost)

                # Energy Usage this Month
                if datetime_now_start.replace(day=1) <= cur_datetime <= datetime_now:
                    energy_usage_this_month += float(kwh)
                    energy_usage_price_this_month += float(cost)

                # Energy Usage this Day 1 day ago
                if yesterday_start <= cur_datetime <= yesterday:
                    energy_usage_this_day_1_day_ago += float(kwh)
                    energy_usage_price_this_day_1_day_ago += float(cost)

                # Energy Usage this Month 1 day ago
                if yesterday_start.replace(day=1) <= cur_datetime <= yesterday:
                    energy_usage_this_month_1_day_ago += float(kwh)
                    energy_usage_price_this_month_1_day_ago += float(cost)

                # Past 48 hrs usage
                hourly_key = cur_datetime.strftime(HOURLY_KEY_DATE_FORMAT)
                if (datetime_now - timedelta(hours=48)) < cur_datetime <= datetime_now:
                    hourly_energy_usage_past_48hr[hourly_key] = {
                        DATA_SUMMARY_KEY_DAY: day,
                        DATA_SUMMARY_KEY_HOUR: hour,
                        DATA_SUMMARY_KEY_DATE: iso_date,
                        DATA_SUMMARY_KEY_VALUE: float(kwh),
                    }
                    hourly_energy_usage_price_past_48hr[hourly_key] = {
                        DATA_SUMMARY_KEY_DAY: day,
                        DATA_SUMMARY_KEY_HOUR: hour,
                        DATA_SUMMARY_KEY_DATE: iso_date,
                        DATA_SUMMARY_KEY_VALUE: float(cost),
                    }

                # Past 2 weeks daily
                daily_key = cur_datetime.strftime(DAILY_KEY_DATE_FORMAT)
                if (
                    (datetime_now_start - timedelta(days=14))
                    < cur_datetime
                    <= datetime_now
                ):
                    if daily_key in daily_energy_usage_past_2weeks:
                        daily_energy_usage_past_2weeks[daily_key][
                            DATA_SUMMARY_KEY_VALUE
                        ] += float(kwh)

                    else:
                        daily_energy_usage_past_2weeks[daily_key] = {
                            DATA_SUMMARY_KEY_DAY: day,
                            DATA_SUMMARY_KEY_HOUR: hour,
                            DATA_SUMMARY_KEY_DATE: iso_date,
                            DATA_SUMMARY_KEY_VALUE: float(kwh),
                        }

                    if daily_key in daily_energy_usage_price_past_2weeks:
                        daily_energy_usage_price_past_2weeks[daily_key][
                            DATA_SUMMARY_KEY_VALUE
                        ] += float(cost)
                    else:
                        daily_energy_usage_price_past_2weeks[daily_key] = {
                            DATA_SUMMARY_KEY_DAY: day,
                            DATA_SUMMARY_KEY_HOUR: hour,
                            DATA_SUMMARY_KEY_DATE: iso_date,
                            DATA_SUMMARY_KEY_VALUE: float(cost),
                        }

            result["energy_usage_this_day"] = round(energy_usage_this_day, 2)
            result["energy_usage_price_this_day"] = round(
                energy_usage_price_this_day, 2
            )
            result["energy_usage_this_month"] = round(energy_usage_this_month, 2)
            result["energy_usage_price_this_month"] = round(
                energy_usage_price_this_month, 2
            )
            result["energy_usage_this_day_1_day_ago"] = round(
                energy_usage_this_day_1_day_ago, 2
            )
            result["energy_usage_price_this_day_1_day_ago"] = round(
                energy_usage_price_this_day_1_day_ago, 2
            )
            result["energy_usage_this_month_1_day_ago"] = round(
                energy_usage_this_month_1_day_ago, 2
            )
            result["energy_usage_price_this_month_1_day_ago"] = round(
                energy_usage_price_this_month_1_day_ago, 2
            )

            for key, value in sorted(hourly_energy_usage_past_48hr.items()):
                hourly_energy_usage_past_48hr[key][DATA_SUMMARY_KEY_VALUE] = round(
                    value[DATA_SUMMARY_KEY_VALUE], 2
                )
            result["hourly_energy_usage_past_48hr"] = hourly_energy_usage_past_48hr

            for key, value in sorted(hourly_energy_usage_price_past_48hr.items()):
                hourly_energy_usage_price_past_48hr[key][
                    DATA_SUMMARY_KEY_VALUE
                ] = round(value[DATA_SUMMARY_KEY_VALUE], 2)
            result[
                "hourly_energy_usage_price_past_48hr"
            ] = hourly_energy_usage_price_past_48hr

            for key, value in sorted(daily_energy_usage_past_2weeks.items()):
                daily_energy_usage_past_2weeks[key][DATA_SUMMARY_KEY_VALUE] = round(
                    value[DATA_SUMMARY_KEY_VALUE], 2
                )
            result["daily_energy_usage_past_2weeks"] = daily_energy_usage_past_2weeks

            for key, value in sorted(daily_energy_usage_price_past_2weeks.items()):
                daily_energy_usage_price_past_2weeks[key][
                    DATA_SUMMARY_KEY_VALUE
                ] = round(value[DATA_SUMMARY_KEY_VALUE], 2)
            result[
                "daily_energy_usage_price_past_2weeks"
            ] = daily_energy_usage_price_past_2weeks

            _LOGGER.debug(
                "SrpDataCoordinator: _async_update_data: min_date: %s; max_date: %s;",
                self.min_date,
                self.max_date,
            )
            _LOGGER.debug(
                "SrpDataCoordinator: _async_update_data: %s",
                result,
            )

        return result
