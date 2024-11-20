"""Coordinator for Powerfox integration."""

from __future__ import annotations

from powerfox import Powerfox, Poweropti

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, LOGGER, SCAN_INTERVAL

class PowerfoxDataUpdateCoordinator(DataUpdateCoordinator[???]):
    """Class to manage fetching Powerfox data from the API."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: Powerfox,
        device: ???,
    ) -> None:
        """Initialize global Powerfox data updater."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.client = client
        self.device = device

    async def _async_update_data(self) -> ???:
        """Fetch data from Powerfox API."""
        return await self.client.device(devic_id=self.device.device_id)