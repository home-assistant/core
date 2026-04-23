"""Coordinator for Aladdin Connect integration."""

from __future__ import annotations

from datetime import timedelta
import logging

import aiohttp
from genie_partner_sdk.client import AladdinConnectClient
from genie_partner_sdk.model import GarageDoor

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)
type AladdinConnectConfigEntry = ConfigEntry[AladdinConnectCoordinator]
SCAN_INTERVAL = timedelta(seconds=15)


class AladdinConnectCoordinator(DataUpdateCoordinator[dict[str, GarageDoor]]):
    """Coordinator for Aladdin Connect integration."""

    config_entry: AladdinConnectConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: AladdinConnectConfigEntry,
        client: AladdinConnectClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            config_entry=entry,
            name="Aladdin Connect Coordinator",
            update_interval=SCAN_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, GarageDoor]:
        """Fetch data from the Aladdin Connect API."""
        try:
            doors = await self.client.get_doors()
        except aiohttp.ClientResponseError as err:
            if 400 <= err.status < 500:
                raise ConfigEntryAuthFailed(err) from err
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

        return {door.unique_id: door for door in doors}
