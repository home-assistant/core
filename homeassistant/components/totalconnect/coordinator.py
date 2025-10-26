"""The totalconnect component."""

from datetime import timedelta
import logging

from total_connect_client.client import TotalConnectClient
from total_connect_client.exceptions import (
    AuthenticationError,
    ServiceUnavailable,
    TotalConnectError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

SCAN_INTERVAL = timedelta(seconds=30)
_LOGGER = logging.getLogger(__name__)

type TotalConnectConfigEntry = ConfigEntry[TotalConnectDataUpdateCoordinator]


class TotalConnectDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Class to fetch data from TotalConnect."""

    config_entry: TotalConnectConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: TotalConnectConfigEntry,
        client: TotalConnectClient,
    ) -> None:
        """Initialize."""
        self.client = client
        super().__init__(
            hass,
            logger=_LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> None:
        """Update data."""
        await self.hass.async_add_executor_job(self.sync_update_data)

    def sync_update_data(self) -> None:
        """Fetch synchronous data from TotalConnect."""
        try:
            for location_id in self.client.locations:
                self.client.locations[location_id].get_panel_meta_data()
        except AuthenticationError as exception:
            # should only encounter if password changes during operation
            raise ConfigEntryAuthFailed(
                "TotalConnect authentication failed during operation."
            ) from exception
        except ServiceUnavailable as exception:
            raise UpdateFailed(
                "Error connecting to TotalConnect or the service is unavailable. "
                "Check https://status.resideo.com/ for outages."
            ) from exception
        except TotalConnectError as exception:
            raise UpdateFailed(exception) from exception
        except ValueError as exception:
            raise UpdateFailed("Unknown state from TotalConnect") from exception
