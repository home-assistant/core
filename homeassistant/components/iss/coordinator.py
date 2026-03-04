"""DataUpdateCoordinator for the ISS integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

import pyiss
from requests.exceptions import ConnectionError as RequestsConnectionError, HTTPError

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


def _update(iss: pyiss.ISS) -> IssData:
    """Retrieve data from the pyiss API."""
    return IssData(
        number_of_people_in_space=iss.number_of_people_in_space(),
        current_location=iss.current_location(),
    )


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

    async def _async_update_data(self) -> IssData:
        """Retrieve data from the pyiss API."""
        try:
            return await self.hass.async_add_executor_job(_update, self._iss)
        except (HTTPError, RequestsConnectionError) as ex:
            raise UpdateFailed("Unable to retrieve data") from ex
