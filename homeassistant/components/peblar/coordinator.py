"""Data update coordinator for Peblar EV chargers."""

from datetime import timedelta

from peblar import PeblarApi, PeblarError, PeblarMeter

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import LOGGER

type PeblarConfigEntry = ConfigEntry[PeblarMeterDataUpdateCoordinator]


class PeblarMeterDataUpdateCoordinator(DataUpdateCoordinator[PeblarMeter]):
    """Class to manage fetching Peblar meter data."""

    def __init__(
        self, hass: HomeAssistant, entry: PeblarConfigEntry, api: PeblarApi
    ) -> None:
        """Initialize the coordinator."""
        self.api = api
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=f"Peblar {entry.title} meter",
            update_interval=timedelta(seconds=10),
        )

    async def _async_update_data(self) -> PeblarMeter:
        """Fetch data from the Peblar device."""
        try:
            return await self.api.meter()
        except PeblarError as err:
            raise UpdateFailed(err) from err
