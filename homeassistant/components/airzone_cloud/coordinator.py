"""The Airzone Cloud integration coordinator."""

from __future__ import annotations

from asyncio import timeout
from datetime import timedelta
import logging
from typing import Any

from aioairzone_cloud.cloudapi import AirzoneCloudApi
from aioairzone_cloud.exceptions import AirzoneCloudError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import AIOAIRZONE_CLOUD_TIMEOUT_SEC, DOMAIN

SCAN_INTERVAL = timedelta(seconds=60)

_LOGGER = logging.getLogger(__name__)

type AirzoneCloudConfigEntry = ConfigEntry[AirzoneUpdateCoordinator]


class AirzoneUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching data from the Airzone Cloud device."""

    config_entry: AirzoneCloudConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: AirzoneCloudConfigEntry,
        airzone: AirzoneCloudApi,
    ) -> None:
        """Initialize."""
        self.airzone = airzone
        self.airzone.set_update_callback(self.async_set_updated_data)

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        async with timeout(AIOAIRZONE_CLOUD_TIMEOUT_SEC):
            try:
                await self.airzone.update()
            except AirzoneCloudError as error:
                raise UpdateFailed(error) from error
            return self.airzone.data()
