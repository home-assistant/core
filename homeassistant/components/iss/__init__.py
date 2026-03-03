"""The iss component."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

import pyiss
import requests
from requests.exceptions import HTTPError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, MAX_CONSECUTIVE_FAILURES

type IssConfigEntry = ConfigEntry[IssDataUpdateCoordinator]

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


@dataclass
class IssData:
    """Dataclass representation of data returned from pyiss."""

    number_of_people_in_space: int
    current_location: dict[str, str]


class IssDataUpdateCoordinator(DataUpdateCoordinator[IssData]):
    """ISS coordinator that tolerates transient API failures."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
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

    async def _async_update_data(self) -> IssData:
        """Fetch data from the ISS API, tolerating transient failures."""
        try:
            data = await self.hass.async_add_executor_job(
                lambda: IssData(
                    number_of_people_in_space=self.iss.number_of_people_in_space(),
                    current_location=self.iss.current_location(),
                )
            )
        except (HTTPError, requests.exceptions.ConnectionError) as err:
            self._consecutive_failures += 1
            if (
                self._consecutive_failures >= MAX_CONSECUTIVE_FAILURES
                or self.data is None
            ):
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


async def async_setup_entry(hass: HomeAssistant, entry: IssConfigEntry) -> bool:
    """Set up this integration using UI."""
    coordinator = IssDataUpdateCoordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    entry.async_on_unload(entry.add_update_listener(update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: IssConfigEntry) -> bool:
    """Handle removal of an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def update_listener(hass: HomeAssistant, entry: IssConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
