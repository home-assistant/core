"""Helpers to help coordinate updates."""

from pypalazzetti.client import PalazzettiClient
from pypalazzetti.exceptions import CommunicationError, ValidationError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, SCAN_INTERVAL

type PalazzettiConfigEntry = ConfigEntry[PalazzettiDataUpdateCoordinator]


class PalazzettiDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Class to manage fetching Palazzetti data from a Palazzetti hub."""

    config_entry: PalazzettiConfigEntry
    client: PalazzettiClient

    def __init__(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Initialize global Palazzetti data updater."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.client = PalazzettiClient(self.config_entry.data[CONF_HOST])

    async def _async_setup(self) -> None:
        try:
            await self.client.connect()
            await self.client.update_state()
        except (CommunicationError, ValidationError) as err:
            raise UpdateFailed(f"Error communicating with the API: {err}") from err

    async def _async_update_data(self) -> None:
        """Fetch data from Palazzetti."""
        try:
            await self.client.update_state()
        except (CommunicationError, ValidationError) as err:
            raise UpdateFailed(f"Error communicating with the API: {err}") from err
