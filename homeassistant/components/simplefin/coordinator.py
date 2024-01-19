"""Data update coordinator for the SimpleFIN integration."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from simplefin4py import SimpleFin

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import LOGGER


class SimpleFinDataUpdateCoordinator(DataUpdateCoordinator[Any]):
    """Data update coordinator for the SimpleFIN integration."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, sf_client: SimpleFin) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=LOGGER,
            name="simplefin",
            update_interval=timedelta(hours=4),
        )
        self.sf_client = sf_client

    async def _async_update_data(self) -> Any:
        """Fetch data for all accounts."""
        return await self.sf_client.fetch_data()
