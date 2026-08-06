"""Data update coordinator for the De Lijn integration."""

from typing import override

from pydelijn import DeLijnAuthError, DeLijnClient, DeLijnError, Passage

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_NUMBER_OF_DEPARTURES,
    CONF_STOP_NUMBER,
    DEFAULT_NUMBER_OF_DEPARTURES,
    DOMAIN,
    LOGGER,
    SCAN_INTERVAL,
)

type DeLijnConfigEntry = ConfigEntry[DeLijnCoordinator]


class DeLijnCoordinator(DataUpdateCoordinator[list[Passage]]):
    """Coordinator that polls upcoming De Lijn passages for a single stop."""

    config_entry: DeLijnConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: DeLijnConfigEntry, client: DeLijnClient
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self._client = client
        self._stop_number = config_entry.data[CONF_STOP_NUMBER]

    @override
    async def _async_update_data(self) -> list[Passage]:
        max_passages = self.config_entry.options.get(
            CONF_NUMBER_OF_DEPARTURES, DEFAULT_NUMBER_OF_DEPARTURES
        )
        try:
            return await self._client.get_passages(self._stop_number, max_passages)
        except DeLijnAuthError as err:
            raise ConfigEntryAuthFailed(
                "The De Lijn API key is no longer valid"
            ) from err
        except DeLijnError as err:
            raise UpdateFailed(
                f"Error communicating with the De Lijn API: {err}"
            ) from err
