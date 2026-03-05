"""Data update coordinator for Homevolt integration."""

from __future__ import annotations

import logging

from homevolt import (
    Homevolt,
    HomevoltAuthenticationError,
    HomevoltConnectionError,
    HomevoltError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL

type HomevoltConfigEntry = ConfigEntry[HomevoltDataUpdateCoordinator]

_LOGGER = logging.getLogger(__name__)


class HomevoltDataUpdateCoordinator(DataUpdateCoordinator[Homevolt]):
    """Class to manage fetching Homevolt data."""

    config_entry: HomevoltConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: HomevoltConfigEntry,
        client: Homevolt,
    ) -> None:
        """Initialize the Homevolt coordinator."""
        self.client = client
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
            config_entry=entry,
        )

    async def _async_update_data(self) -> Homevolt:
        """Fetch data from the Homevolt API."""
        try:
            await self.client.update_info()
        except HomevoltAuthenticationError as err:
            raise ConfigEntryAuthFailed from err
        except (HomevoltConnectionError, HomevoltError) as err:
            raise UpdateFailed(f"Error communicating with device: {err}") from err

        return self.client
