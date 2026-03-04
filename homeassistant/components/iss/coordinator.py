"""DataUpdateCoordinator for the ISS integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

import pyiss
import requests
from requests.exceptions import HTTPError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, MAX_CONSECUTIVE_FAILURES

type IssConfigEntry = ConfigEntry[IssDataUpdateCoordinator]

_LOGGER = logging.getLogger(__name__)


@dataclass
class IssData:
    """Dataclass representation of data returned from pyiss."""

    number_of_people_in_space: int
    current_location: dict[str, str]


class IssDataUpdateCoordinator(DataUpdateCoordinator[IssData]):
    """ISS coordinator that tolerates transient API failures."""

    config_entry: IssConfigEntry

    def __init__(self, hass: HomeAssistant, entry: IssConfigEntry) -> None:
        """Initialize the ISS coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=60),
        )
        self._consecutive_failures = 0
        self.iss = pyiss.ISS()

    def _fetch_iss_data(self) -> IssData:
        """Fetch data from ISS API (blocking)."""
        return IssData(
            number_of_people_in_space=self.iss.number_of_people_in_space(),
            current_location=self.iss.current_location(),
        )

    async def _async_update_data(self) -> IssData:
        """Fetch data from the ISS API, tolerating transient failures."""
        try:
            data = await self.hass.async_add_executor_job(self._fetch_iss_data)
        except (HTTPError, requests.exceptions.ConnectionError) as err:
            self._consecutive_failures += 1
            if self.data is None:
                raise UpdateFailed("Unable to retrieve data") from err
            if self._consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                raise UpdateFailed(
                    f"Unable to retrieve data after {self._consecutive_failures} consecutive update failures"
                ) from err
            _LOGGER.debug(
                "Transient API error (%s/%s), using cached data: %s",
                self._consecutive_failures,
                MAX_CONSECUTIVE_FAILURES,
                err,
            )
            return self.data
        self._consecutive_failures = 0
        return data
