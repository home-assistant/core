"""Coordinator for Powerfox integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, LOGGER, SCAN_INTERVAL

if TYPE_CHECKING:
    from powerfox import Device, Powerfox, Poweropti


class PowerfoxDataUpdateCoordinator(DataUpdateCoordinator[Poweropti]):
    """Class to manage fetching Powerfox data from the API."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: Powerfox,
        device: Device,
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

    async def _async_update_data(self) -> Poweropti:
        """Fetch data from Powerfox API."""
        return await self.client.device(device_id=self.device.device_id)
