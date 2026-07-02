"""Data update coordinator for the Lepro integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import LoproApiClient
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class LoproCoordinator(DataUpdateCoordinator[dict[int, dict[str, Any]]]):
    """Coordinator that fetches the Lepro device list on demand."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: LoproApiClient,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=5),
            config_entry=config_entry,
        )
        self.client = client

    async def _async_update_data(self) -> dict[int, dict[str, Any]]:
        """Fetch device list and return as a dict keyed by device id."""
        try:
            devices = await self.client.async_get_devices()
        except Exception as err:
            raise UpdateFailed(f"Failed to fetch Lepro devices: {err}") from err
        return {device["did"]: device for device in devices}
