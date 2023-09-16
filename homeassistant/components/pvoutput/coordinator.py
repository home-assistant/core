"""DataUpdateCoordinator for the PVOutput integration."""
from __future__ import annotations

from pvo import PVOutput, PVOutputAuthenticationError, PVOutputNoDataError, Status

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_SYSTEM_ID, DOMAIN, LOGGER, SCAN_INTERVAL


class PVOutputDataUpdateCoordinator(DataUpdateCoordinator[Status]):
    """The PVOutput Data Update Coordinator."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the PVOutput coordinator."""
        self.config_entry = entry
        self.pvoutput = PVOutput(
            api_key=entry.data[CONF_API_KEY],
            system_id=entry.data[CONF_SYSTEM_ID],
            session=async_get_clientsession(hass),
        )

        super().__init__(hass, LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)

    async def _async_update_data(self) -> Status:
        """Fetch system status from PVOutput."""
        try:
            return await self.pvoutput.status()
        except PVOutputNoDataError as err:
            raise UpdateFailed("PVOutput has no data available") from err
        except PVOutputAuthenticationError as err:
            raise ConfigEntryAuthFailed from err
