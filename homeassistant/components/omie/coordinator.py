"""Coordinator for the OMIE - Spain and Portugal electricity prices integration."""

from __future__ import annotations

from collections.abc import Mapping
import datetime as dt
import logging
from zoneinfo import ZoneInfo

import pyomie.main as pyomie
from pyomie.model import OMIEResults, SpotData

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.dt import utcnow

from .const import DOMAIN
from .util import get_market_dates, is_published

_LOGGER = logging.getLogger(__name__)

_SCHEDULE_MAX_DELAY = dt.timedelta(seconds=10)
"""To avoid thundering herd, we will fetch from OMIE up to this much time after the OMIE data becomes available."""

type OMIEConfigEntry = ConfigEntry[OMIECoordinator]


class OMIECoordinator(DataUpdateCoordinator[Mapping[dt.date, OMIEResults[SpotData]]]):
    """Coordinator that manages OMIE data for yesterday, today, and tomorrow."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: OMIEConfigEntry,
    ) -> None:
        """Initialize OMIE coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}",
            config_entry=config_entry,
            update_interval=dt.timedelta(minutes=1),
        )
        self.data: Mapping[dt.date, OMIEResults[SpotData]] = {}
        self._client_session = async_get_clientsession(hass)

    async def _async_update_data(self) -> Mapping[dt.date, OMIEResults[SpotData]]:
        """Update OMIE data, fetching data as needed and available."""
        now = utcnow()
        relevant_dates = get_market_dates(ZoneInfo(self.hass.config.time_zone), now)
        published_dates = {date for date in relevant_dates if is_published(date, now)}

        # seed new data with previously-fetched days. these are immutable once fetched.
        data = {
            date: results
            for date, results in self.data.items()
            if date in relevant_dates
        }

        try:
            # off to OMIE for anything that's still missing
            for d in {pd for pd in published_dates if pd not in data}:
                _LOGGER.info("Fetching OMIE data for %s", d)
                if results := await pyomie.spot_price(self._client_session, d):
                    _LOGGER.debug("pyomie.spot_price returned: %s", results)
                    data.update({d: results})
        except Exception as error:
            raise UpdateFailed(str(error)) from error

        _LOGGER.debug("_async_update_data: %s", data)
        return data

    @callback
    def _schedule_refresh(self) -> None:
        """Schedules the next refresh beginning of the next hour."""
        now = dt.datetime.now()
        refresh_at = now.replace(minute=0, second=0) + dt.timedelta(hours=1)
        self.update_interval = refresh_at - now

        _LOGGER.debug("Next refresh at %s", refresh_at.astimezone())
        super()._schedule_refresh()
