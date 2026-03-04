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

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class IssData:
    """Dataclass representation of data returned from pyiss."""

    number_of_people_in_space: int
    current_location: dict[str, str]


class IssCoordinator(DataUpdateCoordinator[IssData]):
    """Coordinator for ISS data."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=60),
        )
        self._iss = pyiss.ISS()

    def _update(self) -> IssData:
        """Retrieve data from the pyiss API."""
        return IssData(
            number_of_people_in_space=self._iss.number_of_people_in_space(),
            current_location=self._iss.current_location(),
        )

    async def _async_update_data(self) -> IssData:
        """Retrieve data from the pyiss API."""
        try:
            return await self.hass.async_add_executor_job(self._update)
        except (HTTPError, requests.exceptions.ConnectionError) as ex:
            raise UpdateFailed("Unable to retrieve data") from ex
