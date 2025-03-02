"""Zeversolar coordinator."""

from __future__ import annotations

from datetime import timedelta
import logging

import zeversolar

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ZeversolarCoordinator(DataUpdateCoordinator[zeversolar.ZeverSolarData]):
    """Data update coordinator."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=1),
        )
        self._client = zeversolar.ZeverSolarClient(host=entry.data[CONF_HOST])

    async def _async_update_data(self) -> zeversolar.ZeverSolarData:
        """Fetch the latest data from the source."""
        return await self.hass.async_add_executor_job(self._client.get_data)
