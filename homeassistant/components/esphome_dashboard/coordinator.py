"""Coordinator for ESPHome Dashboard integration."""

from __future__ import annotations

from datetime import timedelta
import logging

import aiohttp
from esphome_dashboard_api import ConfiguredDevice, ESPHomeDashboardAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=5)


class ESPHomeDashboardCoordinator(DataUpdateCoordinator[dict[str, ConfiguredDevice]]):
    """Class to manage fetching ESPHome Dashboard data."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: ESPHomeDashboardAPI,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="ESPHome Dashboard",
            update_interval=SCAN_INTERVAL,
            config_entry=config_entry,
        )
        self.api = api

    async def _async_update_data(self) -> dict[str, ConfiguredDevice]:
        """Fetch device data from the dashboard."""
        try:
            devices_data = await self.api.get_devices()
            configured_devices: list[ConfiguredDevice] = devices_data.get(
                "configured", []
            )

            # Return devices indexed by their name
            return {device["name"]: device for device in configured_devices}
        except aiohttp.ClientResponseError as err:
            if err.status in (401, 403):
                raise ConfigEntryAuthFailed(
                    "Authentication failed. Please update your credentials."
                ) from err
            raise UpdateFailed(f"Error communicating with dashboard: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Error communicating with dashboard: {err}") from err
