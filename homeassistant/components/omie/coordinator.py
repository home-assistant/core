"""Coordinator for the OMIE - Spain and Portugal electricity prices integration."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, time, timedelta
import logging
import random
from zoneinfo import ZoneInfo

import pyomie.main as pyomie
from pyomie.model import OMIEResults, SpotData

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HassJob, HassJobType, HomeAssistant, callback
from homeassistant.helpers import event
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.dt import utcnow

from .const import CET, DOMAIN

_LOGGER = logging.getLogger(__name__)

_SCHEDULE_MAX_DELAY = timedelta(seconds=10)
"""To avoid thundering herd, we will fetch from OMIE up to this much time after the OMIE data becomes available."""

_OMIE_PUBLISH_TIME_CET = time(hour=13, minute=30)
"""The time by which intraday market results (for the next day) will have been published to omie.es."""


class OMIECoordinator(DataUpdateCoordinator[Mapping[date, OMIEResults[SpotData]]]):
    """Coordinator that manages OMIE data for yesterday, today, and tomorrow."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        *,
        spot_price_fetcher=None,
    ) -> None:
        """Initialize OMIE coordinator."""
        super().__init__(hass, _LOGGER, name=f"{DOMAIN}", config_entry=config_entry)
        self.data: Mapping[date, OMIEResults[SpotData]] = {}
        self._client_session = async_get_clientsession(hass)

        # Dependency injection for testing
        self._spot_price_fetcher = spot_price_fetcher or pyomie.spot_price

        # Random delay to avoid thundering herd
        delay_micros = random.randint(0, _SCHEDULE_MAX_DELAY.seconds * 10**6)
        self._schedule_second = delay_micros // 10**6
        self._schedule_microsecond = delay_micros % 10**6
        self.__job = HassJob(
            self._handle_refresh_interval,
            "OMIECoordinator",
            job_type=HassJobType.Coroutinefunction,
        )

    async def _async_update_data(self) -> Mapping[date, OMIEResults[SpotData]]:
        """Update OMIE data, fetching data as needed and available."""
        now = utcnow()
        relevant_dates = _get_market_dates(ZoneInfo(self.hass.config.time_zone), now)
        published_dates = {date for date in relevant_dates if _is_published(date, now)}

        # seed new data with previously-fetched days. these are immutable once fetched.
        data = {
            date: results
            for date, results in self.data.items()
            if date in relevant_dates
        }

        try:
            # off to OMIE for anything that's still missing
            for d in {pd for pd in published_dates if pd not in data}:
                _LOGGER.debug("Fetching data for %s", d)
                if results := await self._spot_price_fetcher(self._client_session, d):
                    data.update({d: results})
        except Exception as error:
            raise UpdateFailed(str(error)) from error

        _LOGGER.debug("_async_update_data: %s", data)
        return data

    @callback
    def _schedule_refresh(self) -> None:
        """Schedule the next refresh at the top of the next hour."""
        if self.config_entry and self.config_entry.pref_disable_polling:
            return

        # We do not cancel the debouncer here. If the refresh interval is shorter
        # than the debouncer cooldown, this would cause the debounce to never be called
        self._async_unsub_refresh()

        # Schedule for the next hour boundary
        now_cet = utcnow().astimezone(CET)
        next_hour = now_cet.replace(
            minute=0,
            second=self._schedule_second,
            microsecond=self._schedule_microsecond,
        ) + timedelta(hours=1)

        next_refresh = next_hour.astimezone()

        _LOGGER.debug(
            "Scheduling next refresh at %s (CET: %s)",
            next_refresh,
            next_hour,
        )

        self._unsub_refresh = event.async_track_point_in_utc_time(
            self.hass, self.__job, next_refresh
        )


def _get_market_dates(local_tz: ZoneInfo, now_time: datetime) -> set[date]:
    """Returns the intraday market date(s) whose data we need to fetch."""
    min_max = [_OMIE_PUBLISH_TIME_CET.min, _OMIE_PUBLISH_TIME_CET.max]
    return {
        datetime.combine(now_time.astimezone(local_tz), t, tzinfo=local_tz)
        .astimezone(CET)
        .date()
        for t in min_max
    }


def _is_published(market_date: date, fetch_time: datetime) -> bool:
    """Returns whether OMIE data for a given date is expected to have been published at any point in time."""
    publish_date = market_date - timedelta(days=1)
    publish_hour = _OMIE_PUBLISH_TIME_CET
    publish_time = datetime.combine(publish_date, publish_hour, tzinfo=CET)

    return fetch_time >= publish_time
