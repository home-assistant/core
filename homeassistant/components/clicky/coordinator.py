"""Coordinator to handle Clicky API access."""

from datetime import timedelta
import logging
from typing import Any, override

from pyclicky import AuthenticationError, ClickyAPIError, ClickyClient, ConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type ClickyConfigEntry = ConfigEntry[ClickyCoordinator]


class ClickyCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Handle fetching Clicky data and updating sensors."""

    config_entry: ClickyConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: ClickyConfigEntry, client: ClickyClient
    ) -> None:
        """Initialize the data handler."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=1),
        )

        self.client = client

    @override
    async def _async_update_data(
        self,
    ) -> dict[str, Any]:
        """Fetch data from API endpoint."""
        try:
            async with self.client:
                visitors_online = await self.client.visitors_online()
                time_total = await self.client.time_total()
        except AuthenticationError as error:
            raise ConfigEntryAuthFailed("API authentication failed") from error
        except ConnectionError as error:
            raise UpdateFailed(f"Couldn't connect to API: {error}") from error
        except ClickyAPIError as error:
            raise UpdateFailed(f"Error fetching data from API: {error}") from error

        return {
            "visitorsOnline": visitors_online.value
            if visitors_online.value is not None
            else 0,
            "timeTotal": time_total.value if time_total.value is not None else 0,
        }
