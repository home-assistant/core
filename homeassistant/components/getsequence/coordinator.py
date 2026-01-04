"""DataUpdateCoordinator for Sequence integration."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
from GetSequenceIoApiClient import (
    SequenceApiClient,
    SequenceApiError,
    SequenceAuthError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class SequenceDataUpdateCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Class to manage fetching data from the Sequence API."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        session: aiohttp.ClientSession,
    ) -> None:
        """Initialize the coordinator."""
        self.api = SequenceApiClient(session, entry.data[CONF_ACCESS_TOKEN])

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
            config_entry=entry,
        )

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Fetch account data from Sequence API."""
        try:
            accounts_data = await self.api.async_get_accounts()
        except SequenceAuthError as err:
            raise ConfigEntryAuthFailed(
                "Authentication failed. Please reauthenticate."
            ) from err
        except SequenceApiError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

        # Extract the accounts list from the API response
        return accounts_data.get("data", {}).get("accounts", [])
