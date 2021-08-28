"""Coordinator for Sonarr."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from sonarr import Sonarr, SonarrAccessRestricted, SonarrError

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.util.dt as dt_util

from .const import (
    CONF_UPCOMING_DAYS,
    CONF_WANTED_MAX_ITEMS,
    DEFAULT_UPCOMING_DAYS,
    DEFAULT_WANTED_MAX_ITEMS,
    DOMAIN,
)

SCAN_INTERVAL = timedelta(seconds=30)
_LOGGER = logging.getLogger(__name__)


class SonarrDataUpdateCoordinator(DataUpdateCoordinator[dict]):
    """Class to manage fetching Sonarr data."""

    sonarr: Sonarr
    datapoints: list
    upcoming_days: int
    wanted_max_items: int

    def __init__(
        self, hass: HomeAssistant, *, sonarr: Sonarr, options: dict[str, Any]
    ) -> None:
        """Initialize global Sonarr data updater."""
        self.sonarr = sonarr

        self.upcoming_days = options.get(CONF_UPCOMING_DAYS, DEFAULT_UPCOMING_DAYS)
        self.wanted_max_items = options.get(
            CONF_WANTED_MAX_ITEMS, DEFAULT_WANTED_MAX_ITEMS
        )

        self.datapoints = []

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    def enable_datapoint(self, datapoint: str) -> None:
        """Enable collection of a datapoint from its respective endpoint."""
        if datapoint not in self.datapoints:
            self.datapoints.append(datapoint)

    def disable_datapoint(self, datapoint: str) -> None:
        """Disable collection of a datapoint from its respective endpoint."""
        self.datapoints.remove(datapoint)

    def get_datapoint(self, datapoint: str) -> Any:
        """Fetch datapoint from its respective endpoint."""
        if datapoint == "commands":
            return self.sonarr.commands()
        if datapoint == "queue":
            return self.sonarr.queue()
        if datapoint == "series":
            return self.sonarr.series()
        if datapoint == "upcoming":
            local = dt_util.start_of_local_day().replace(microsecond=0)
            start = dt_util.as_utc(local)
            end = start + timedelta(days=self.upcoming_days)

            return self.sonarr.calendar(start=start.isoformat(), end=end.isoformat())
        if datapoint == "wanted":
            return self.sonarr.wanted(page_size=self.wanted_max_items)

    async def _async_update_data(self) -> dict:
        """Fetch data from Sonarr."""
        try:
            await self.sonarr.update()

            data = dict(
                zip(
                    self.datapoints,
                    await asyncio.gather(
                        *(
                            self.get_datapoint(datapoint)
                            for datapoint in self.datapoints
                        ),
                    ),
                )
            )

            return data
        except SonarrAccessRestricted as err:
            raise ConfigEntryAuthFailed(
                "API Key is no longer valid. Please reauthenticate"
            ) from err
        except SonarrError as error:
            raise UpdateFailed(f"Invalid response from API: {error}") from error
