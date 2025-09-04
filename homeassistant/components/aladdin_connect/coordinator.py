"""Coordinator for Aladdin Connect integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from genie_partner_sdk.client import AladdinConnectClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .models import AladdinConnectGarageDoor

_LOGGER = logging.getLogger(__name__)
type AladdinConnectConfigEntry = ConfigEntry[dict[str, AladdinConnectCoordinator]]
SCAN_INTERVAL = timedelta(seconds=15)


class AladdinConnectCoordinator(DataUpdateCoordinator[AladdinConnectGarageDoor]):
    """Coordinator for Aladdin Connect integration."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: AladdinConnectConfigEntry,
        client: AladdinConnectClient,
        garage_door: AladdinConnectGarageDoor,
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

    async def _async_update_data(self) -> AladdinConnectGarageDoor:
        """Fetch data from the Aladdin Connect API."""
        await self.client.update_door(self.data.device_id, self.data.door_number)
        self.data.status, self.data.battery_level = (
            self.client.get_door_status(self.data.device_id, self.data.door_number),
            self.client.get_battery_status(self.data.device_id, self.data.door_number),
        )
        return self.data
