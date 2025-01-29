"""Coordinator for UpCloud."""

from __future__ import annotations

from datetime import timedelta
import logging

import upcloud_api

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


type UpCloudConfigEntry = ConfigEntry[UpCloudDataUpdateCoordinator]


class UpCloudDataUpdateCoordinator(
    DataUpdateCoordinator[dict[str, upcloud_api.Server]]
):
    """UpCloud data update coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        config_entry: UpCloudConfigEntry,
        cloud_manager: upcloud_api.CloudManager,
        update_interval: timedelta,
        username: str,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{username}@UpCloud",
            update_interval=update_interval,
        )
        self.cloud_manager = cloud_manager

    async def async_update_config(self, config_entry: UpCloudConfigEntry) -> None:
        """Handle config update."""
        self.update_interval = timedelta(
            seconds=config_entry.options[CONF_SCAN_INTERVAL]
        )

    async def _async_update_data(self) -> dict[str, upcloud_api.Server]:
        return {
            x.uuid: x
            for x in await self.hass.async_add_executor_job(
                self.cloud_manager.get_servers
            )
        }
