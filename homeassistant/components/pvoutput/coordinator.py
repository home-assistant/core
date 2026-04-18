"""DataUpdateCoordinator for the PVOutput integration."""

from __future__ import annotations

from pvo import (
    PVOutput,
    PVOutputAuthenticationError,
    PVOutputConnectionError,
    PVOutputError,
    PVOutputNoDataError,
    Status,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_SYSTEM_ID, DOMAIN, LOGGER, SCAN_INTERVAL

type PvOutputConfigEntry = ConfigEntry[PVOutputDataUpdateCoordinator]


class PVOutputDataUpdateCoordinator(DataUpdateCoordinator[Status]):
    """The PVOutput Data Update Coordinator."""

    config_entry: PvOutputConfigEntry

    def __init__(self, hass: HomeAssistant, entry: PvOutputConfigEntry) -> None:
        """Initialize the PVOutput coordinator."""
        self.pvoutput = PVOutput(
            api_key=entry.data[CONF_API_KEY],
            system_id=entry.data[CONF_SYSTEM_ID],
            session=async_get_clientsession(hass),
        )

        super().__init__(
            hass, LOGGER, config_entry=entry, name=DOMAIN, update_interval=SCAN_INTERVAL
        )

    async def _async_update_data(self) -> Status:
        """Fetch system status from PVOutput."""
        try:
            return await self.pvoutput.status()
        except PVOutputAuthenticationError as err:
            raise ConfigEntryAuthFailed from err
        except PVOutputNoDataError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="no_data_available",
            ) from err
        except PVOutputConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="communication_error",
            ) from err
        except PVOutputError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="unknown_error",
            ) from err
