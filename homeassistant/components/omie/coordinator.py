"""Coordinator for the OMIE - Spain and Portugal electricity prices integration."""

from __future__ import annotations

import datetime as dt
from datetime import timedelta
import logging
from logging import DEBUG

import pyomie.main as pyomie
from pyomie.model import OMIEResults, SpotData

from homeassistant import util
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .util import CET

_LOGGER = logging.getLogger(__name__)

_SCHEDULE_MAX_DELAY = dt.timedelta(seconds=10)
"""To avoid thundering herd, we will fetch from OMIE up to this much time after the OMIE
 data becomes available."""

_UPDATE_INTERVAL_PADDING = timedelta(seconds=1)
"""Padding to add to the update interval to work around early refresh scheduling by
 DataUpdateCoordinator."""

type OMIEConfigEntry = ConfigEntry[OMIECoordinator]


class OMIECoordinator(DataUpdateCoordinator[OMIEResults[SpotData]]):
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
        self._client_session = async_get_clientsession(hass)

    async def _async_update_data(self) -> OMIEResults[SpotData]:
        """Update OMIE data, fetching the current CET day."""
        cet_today = util.dt.now().astimezone(CET).date()
        if self.data and self.data.market_date == cet_today:
            data = self.data
        else:
            data = await self._spot_price(cet_today)

        self._set_update_interval()
        return data

    def _set_update_interval(self) -> None:
        """Schedules the next refresh at the start of the next quarter-hour."""
        now = util.dt.now()
        self.update_interval = calc_update_interval(now)
        if _LOGGER.isEnabledFor(DEBUG):
            _LOGGER.debug(
                "Next refresh at %s", (now + self.update_interval).isoformat()
            )

    async def _spot_price(self, date: dt.date) -> OMIEResults[SpotData]:
        _LOGGER.debug("Fetching OMIE spot data for %s", date)
        return await pyomie.spot_price(self._client_session, date)


def calc_update_interval(now: dt.datetime) -> dt.timedelta:
    """Calculates the update_interval needed to trigger at the next 15-minute boundary."""
    minutes_floored = now.minute // 15 * 15
    previous_15m = now.replace(minute=minutes_floored, second=0, microsecond=0)

    next_15m = previous_15m + dt.timedelta(minutes=15)
    return next_15m - now + _UPDATE_INTERVAL_PADDING
