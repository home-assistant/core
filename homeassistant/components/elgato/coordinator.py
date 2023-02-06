"""DataUpdateCoordinator for Elgato."""
from dataclasses import dataclass

from elgato import Elgato, ElgatoConnectionError, Info, Settings, State

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, SCAN_INTERVAL


@dataclass
class ElgatoData:
    """Elgato data stored in the DataUpdateCoordinator."""

    info: Info
    settings: Settings
    state: State


class ElgatoDataUpdateCoordinator(DataUpdateCoordinator[ElgatoData]):
    """Class to manage fetching Elgato data."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.config_entry = entry
        self.client = Elgato(
            entry.data[CONF_HOST],
            port=entry.data[CONF_PORT],
            session=async_get_clientsession(hass),
        )
        super().__init__(
            hass,
            LOGGER,
            name=f"{DOMAIN}_{entry.data[CONF_HOST]}",
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> ElgatoData:
        """Fetch data from the Elgato device."""
        try:
            return ElgatoData(
                info=await self.client.info(),
                settings=await self.client.settings(),
                state=await self.client.state(),
            )
        except ElgatoConnectionError as err:
            raise UpdateFailed(err) from err
