"""Coordinator for the OMIE - Spain and Portugal electricity prices integration."""

from __future__ import annotations

import datetime as dt
from datetime import timedelta
import logging

import pyomie.main as pyomie
from pyomie.model import OMIEResults, SpotData

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .util import CET, current_quarter_hour_cet

_LOGGER = logging.getLogger(__name__)

_UPDATE_INTERVAL_PADDING = timedelta(seconds=1)
"""Padding to add to the update interval to work around early refresh scheduling by
 DataUpdateCoordinator."""

type OMIEConfigEntry = ConfigEntry[OMIECoordinator]


class OMIECoordinator(DataUpdateCoordinator[OMIEResults[SpotData]]):
    """Coordinator that manages OMIE data for the current CET day."""

    def __init__(self, hass: HomeAssistant, config_entry: OMIEConfigEntry) -> None:
        """Initialize OMIE coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=config_entry,
            update_interval=dt.timedelta(minutes=1),
        )
        self._client_session = async_get_clientsession(hass)

    async def _async_update_data(self) -> OMIEResults[SpotData]:
        """Update OMIE data, fetching the current CET day."""
        cet_today = dt_util.now().astimezone(CET).date()
        if self.data and self.data.market_date == cet_today:
            data = self.data
        else:
            data = await self._spot_price(cet_today)

        self._set_update_interval()
        return data

    def _set_update_interval(self) -> None:
        """Schedule the next refresh at the start of the next quarter-hour."""
        now = dt_util.now()
        self.update_interval = calc_update_interval(now)
        _LOGGER.debug("Next refresh at %s", (now + self.update_interval).isoformat())

    async def _spot_price(self, date: dt.date) -> OMIEResults[SpotData]:
        """Fetch OMIE spot price data for the given date."""
        _LOGGER.debug("Fetching OMIE spot data for %s", date)
        return await pyomie.spot_price(self._client_session, date)


def calc_update_interval(now: dt.datetime) -> dt.timedelta:
    """Calculate the update_interval needed to trigger at the next 15-minute boundary."""
    current_quarter = current_quarter_hour_cet(now)
    next_quarter = current_quarter + dt.timedelta(minutes=15)

    return next_quarter - now + _UPDATE_INTERVAL_PADDING
