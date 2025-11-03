"""The Airthings integration."""

from datetime import timedelta
import logging

from airthings import Airthings, AirthingsDevice, AirthingsError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(minutes=6)

type AirthingsConfigEntry = ConfigEntry[AirthingsDataUpdateCoordinator]


class AirthingsDataUpdateCoordinator(DataUpdateCoordinator[dict[str, AirthingsDevice]]):
    """Coordinator for Airthings data updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        airthings: Airthings,
        config_entry: AirthingsConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_method=self._update_method,
            update_interval=SCAN_INTERVAL,
        )
        self.airthings = airthings

    async def _update_method(self) -> dict[str, AirthingsDevice]:
        """Get the latest data from Airthings."""
        try:
            return await self.airthings.update_devices()  # type: ignore[no-any-return]
        except AirthingsError as err:
            raise UpdateFailed(f"Unable to fetch data: {err}") from err
