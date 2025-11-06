"""Coordinator for the OMIE - Spain and Portugal electricity prices integration."""

from __future__ import annotations

from collections.abc import Mapping
import datetime as dt
import logging

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
        """Update OMIE data, fetching the current CET day."""
        cet_today = util.dt.now().astimezone(CET).date()
        spot_data = self.data.get(cet_today) or await self.__spot_price(cet_today)

        data = {cet_today: spot_data} if spot_data else {}
        self._set_update_interval()
        return data

    def _set_update_interval(self) -> None:
        """Schedules the next refresh at the start of the next quarter-hour."""
        now = dt.datetime.now()
        now_quarter_minute = now.minute // 15 * 15
        refresh_at = now.replace(
            minute=now_quarter_minute, second=0, microsecond=0
        ) + dt.timedelta(minutes=15)
        self.update_interval = refresh_at - now

        _LOGGER.debug("Next refresh at %s", refresh_at.astimezone())

    async def __spot_price(self, date: dt.date) -> OMIEResults[SpotData] | None:
        _LOGGER.debug("Fetching OMIE spot data for %s", date)
        return await pyomie.spot_price(self._client_session, date)
