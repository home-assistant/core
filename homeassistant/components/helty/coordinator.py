"""DataUpdateCoordinator for the Helty Flow integration."""

import logging

from pyhelty import HeltyClient, HeltyConnectionError, HeltyData, HeltyError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

type HeltyConfigEntry = ConfigEntry[HeltyDataUpdateCoordinator]


class HeltyDataUpdateCoordinator(DataUpdateCoordinator[HeltyData]):
    """Coordinate a single poll of the Helty unit for all entities."""

    config_entry: HeltyConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: HeltyConfigEntry,
        client: HeltyClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> HeltyData:
        try:
            return await self.client.async_get_data()
        except HeltyConnectionError as err:
            raise UpdateFailed(f"Error communicating with Helty unit: {err}") from err
        except HeltyError as err:
            raise UpdateFailed(f"Unexpected response from Helty unit: {err}") from err
