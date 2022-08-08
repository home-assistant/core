"""JustNimbus coordinator."""
from __future__ import annotations

from datetime import timedelta
import logging

import justnimbus

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_SCAN_INTERVAL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class JustNimbusCoordinator(DataUpdateCoordinator[justnimbus.JustNimbusModel]):
    """Data update coordinator."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=entry.data[CONF_SCAN_INTERVAL]),
        )
        self._entry = entry
        self._client = justnimbus.JustNimbusClient(
            client_id=self._entry.data[CONF_CLIENT_ID]
        )

    @property
    def entry_id(self) -> str:
        """Return entry ID."""
        return self._entry.entry_id

    async def _async_update_data(self) -> justnimbus.JustNimbusModel:
        """Fetch the latest data from the source."""
        return await self.hass.async_add_executor_job(self.get_data)

    def get_data(self) -> justnimbus.JustNimbusModel:
        """Get data from the API."""
        return self._client.get_data()
