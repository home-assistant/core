"""DataUpdateCoordinator for BirdNET-Go."""

from typing import override

from aiobirdnetgo import (
    BirdNetGoAuthenticationError,
    BirdNetGoClient,
    BirdNetGoConnectionError,
    BirdNetGoError,
    BirdNetGoTimeoutError,
    DashboardKPIs,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, SCAN_INTERVAL

type BirdNetGoConfigEntry = ConfigEntry[BirdNetGoDataUpdateCoordinator]


class BirdNetGoDataUpdateCoordinator(DataUpdateCoordinator[DashboardKPIs]):
    """Class to manage fetching BirdNET-Go data."""

    config_entry: BirdNetGoConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: BirdNetGoConfigEntry,
        client: BirdNetGoClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_{config_entry.title}",
            update_interval=SCAN_INTERVAL,
        )
        self.client = client

    @override
    async def _async_update_data(self) -> DashboardKPIs:
        """Fetch data from BirdNET-Go."""
        try:
            return await self.client.get_kpis()
        except BirdNetGoAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                f"Authentication failed for {self.client.base_url}"
            ) from err
        except (BirdNetGoConnectionError, BirdNetGoTimeoutError) as err:
            raise UpdateFailed(
                f"Error communicating with BirdNET-Go at {self.client.base_url}: {err}"
            ) from err
        except BirdNetGoError as err:
            raise UpdateFailed(
                f"Unexpected error communicating with BirdNET-Go: {err}"
            ) from err
