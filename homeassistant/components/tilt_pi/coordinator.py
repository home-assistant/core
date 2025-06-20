"""Data update coordinator for Tilt Pi."""

from datetime import timedelta
from typing import Final

from tiltpi import TiltHydrometerData, TiltPiClient, TiltPiError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import LOGGER

SCAN_INTERVAL: Final = timedelta(seconds=60)

type TiltPiConfigEntry = ConfigEntry[TiltPiDataUpdateCoordinator]


class TiltPiDataUpdateCoordinator(DataUpdateCoordinator[dict[str, TiltHydrometerData]]):
    """Class to manage fetching Tilt Pi data."""

    config_entry: TiltPiConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: TiltPiConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name="Tilt Pi",
            update_interval=SCAN_INTERVAL,
        )
        self._api = TiltPiClient(
            host=config_entry.data[CONF_HOST],
            port=config_entry.data[CONF_PORT],
            session=async_get_clientsession(hass),
        )
        self.identifier = config_entry.entry_id

    async def _async_update_data(self) -> dict[str, TiltHydrometerData]:
        """Fetch data from Tilt Pi and return as a dict keyed by mac_id."""
        try:
            hydrometers = await self._api.get_hydrometers()
        except TiltPiError as err:
            raise UpdateFailed(f"Error communicating with Tilt Pi: {err}") from err

        return {h.mac_id: h for h in hydrometers}
