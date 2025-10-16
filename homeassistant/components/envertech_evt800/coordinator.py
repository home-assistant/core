"""Coordinator for Envertech EVT800 integration."""

from datetime import timedelta
import logging
from typing import Any

import pyenvertechevt800

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class EnvertechEVT800Coordinator(DataUpdateCoordinator):
    """Data update coordinator for Envertech EVT800."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: pyenvertechevt800.EnvertechEVT800,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
            config_entry=config_entry,
        )
        self.client = client
        client.set_data_listener(self.async_set_updated_data)

    async def _async_update_data(self) -> Any:
        """Fetch data from the device."""
        return self.client.data
