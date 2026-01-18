"""DataUpdateCoordinator for Liebherr integration."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from pyliebherrhomeapi import (
    DeviceState,
    LiebherrClient,
    LiebherrConnectionError,
    LiebherrTimeoutError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=60)


class LiebherrCoordinator(DataUpdateCoordinator[dict[str, DeviceState]]):
    """Class to manage fetching Liebherr data from the API for all devices."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: LiebherrClient,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
            config_entry=config_entry,
        )
        self.client = client
        self.device_ids: list[str] = []

    async def _async_update_data(self) -> dict[str, DeviceState]:
        """Fetch data from API for all devices."""
        try:
            # Fetch all device states in parallel to minimize API calls
            results = await asyncio.gather(
                *(
                    self.client.get_device_state(device_id)
                    for device_id in self.device_ids
                )
            )
            return dict(zip(self.device_ids, results, strict=False))
        except LiebherrTimeoutError as err:
            raise UpdateFailed(f"Timeout communicating with API: {err}") from err
        except LiebherrConnectionError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
