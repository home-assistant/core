"""Coordinator for the OMIE - Spain and Portugal electricity prices integration."""

from __future__ import annotations

from collections.abc import Mapping
import datetime as dt
import logging
from zoneinfo import ZoneInfo

import pyomie.main as pyomie
from pyomie.model import OMIEResults, SpotData

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .util import get_market_dates

_LOGGER = logging.getLogger(__name__)

_SCHEDULE_MAX_DELAY = dt.timedelta(seconds=10)
"""To avoid thundering herd, we will fetch from OMIE up to this much time after the OMIE data becomes available."""

type OMIEConfigEntry = ConfigEntry[OMIECoordinator]


class OMIECoordinator(DataUpdateCoordinator[Mapping[dt.date, OMIEResults[SpotData]]]):
    """Coordinator that manages OMIE data for yesterday, today, and tomorrow."""

    def __init__(self, hass: HomeAssistant, config_entry: OMIEConfigEntry) -> None:
        """Initialize OMIE coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}",
            config_entry=config_entry,
            update_interval=dt.timedelta(minutes=1),
        )
        self.data = {}
        self._client_session = async_get_clientsession(hass)

    async def _async_update_data(self) -> Mapping[dt.date, OMIEResults[SpotData]]:
        """Update OMIE data, fetching data as needed and available."""
        now = dt.datetime.now(ZoneInfo(self.hass.config.time_zone))
        market_dates = get_market_dates(now)

        # seed new data with previously-fetched days. these are immutable once fetched.
        data = {
            date: results for date, results in self.data.items() if date in market_dates
        }

        # fetch missing days from OMIE
        for date in {d for d in market_dates if d not in data}:
            _LOGGER.debug("Fetching OMIE data for %s", date)
            if results := await pyomie.spot_price(self._client_session, date):
                _LOGGER.debug("pyomie.spot_price returned: %s", results)
                data.update({date: results})

        self._set_update_interval()
        _LOGGER.debug("Received data: %s", data)
        return data

    def _set_update_interval(self) -> None:
        """Schedules the next refresh at the start of the next hour."""
        now = dt.datetime.now()
        refresh_at = now.replace(minute=0, second=0) + dt.timedelta(hours=1)
        self.update_interval = refresh_at - now

        _LOGGER.debug("Next refresh at %s", refresh_at.astimezone())
