"""Data update coordinator for RDW."""

from __future__ import annotations

from vehicle import RDW, RDWConnectionError, RDWError, Vehicle

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_LICENSE_PLATE, DOMAIN, LOGGER, SCAN_INTERVAL

type RDWConfigEntry = ConfigEntry[RDWDataUpdateCoordinator]


class RDWDataUpdateCoordinator(DataUpdateCoordinator[Vehicle]):
    """Class to manage fetching RDW data."""

    config_entry: RDWConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: RDWConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_APK",
            update_interval=SCAN_INTERVAL,
        )
        self._rdw = RDW(
            session=async_get_clientsession(hass),
            license_plate=config_entry.data[CONF_LICENSE_PLATE],
        )

    async def _async_update_data(self) -> Vehicle:
        """Fetch data from RDW."""
        try:
            return await self._rdw.vehicle()
        except RDWConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="communication_error",
            ) from err
        except RDWError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="unknown_error",
            ) from err
