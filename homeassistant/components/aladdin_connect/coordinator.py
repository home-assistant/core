"""Coordinator for Aladdin Connect integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from genie_partner_sdk.client import AladdinConnectClient
from genie_partner_sdk.model import GarageDoor

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
type AladdinConnectConfigEntry = ConfigEntry[dict[str, AladdinConnectCoordinator]]
SCAN_INTERVAL = timedelta(seconds=15)


class AladdinConnectCoordinator(DataUpdateCoordinator[GarageDoor]):
    """Coordinator for Aladdin Connect integration."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: AladdinConnectConfigEntry,
        client: AladdinConnectClient,
        garage_door: GarageDoor,
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
        self.data = garage_door

    async def _async_update_data(self) -> GarageDoor:
        """Fetch data from the Aladdin Connect API."""
        await self.client.update_door(self.data.device_id, self.data.door_number)
        return self.data
