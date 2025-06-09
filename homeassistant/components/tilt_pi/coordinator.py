"""Data update coordinator for Tilt Pi."""

import logging

from tiltpi import TiltPiClient, TiltPiError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import SCAN_INTERVAL
from .model import TiltHydrometerData

_LOGGER = logging.getLogger(__name__)

type TiltPiConfigEntry = ConfigEntry[TiltPiDataUpdateCoordinator]


class TiltPiDataUpdateCoordinator(DataUpdateCoordinator[dict[str, TiltHydrometerData]]):
    """Class to manage fetching Tilt Pi data."""

    config_entry: TiltPiConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: TiltPiConfigEntry,
        client: TiltPiClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Tilt Pi",
            update_interval=SCAN_INTERVAL,
        )
        self.config_entry = config_entry
        self._api = client
        self.identifier = config_entry.entry_id

    async def _async_update_data(self) -> dict[str, TiltHydrometerData]:
        """Fetch data from Tilt Pi and return as a dict keyed by mac_id."""
        try:
            hydrometers = await self._api.get_hydrometers()
            return {h.mac_id: h for h in hydrometers}
        except TiltPiError as err:
            raise UpdateFailed(f"Error communicating with Tilt Pi: {err}") from err
