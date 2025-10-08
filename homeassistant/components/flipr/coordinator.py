"""DataUpdateCoordinator for flipr integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from flipr_api import FliprAPIRestClient
from flipr_api.exceptions import FliprError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


@dataclass
class FliprData:
    """The Flipr data class."""

    flipr_coordinators: list[FliprDataUpdateCoordinator]
    hub_coordinators: list[FliprHubDataUpdateCoordinator]


type FliprConfigEntry = ConfigEntry[FliprData]


class BaseDataUpdateCoordinator[_DataT](DataUpdateCoordinator[_DataT]):
    """Parent class to hold Flipr and Hub data retrieval."""

    config_entry: FliprConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: FliprConfigEntry,
        client: FliprAPIRestClient,
        flipr_or_hub_id: str,
    ) -> None:
        """Initialize."""
        self.device_id = flipr_or_hub_id
        self.client = client

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"Flipr or Hub data measure for {self.device_id}",
            update_interval=timedelta(minutes=15),
        )


class FliprDataUpdateCoordinator(BaseDataUpdateCoordinator[dict[str, Any]]):
    """Class to hold Flipr data retrieval."""

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API endpoint."""
        try:
            data = await self.hass.async_add_executor_job(
                self.client.get_pool_measure_latest, self.device_id
            )
        except FliprError as error:
            raise UpdateFailed(error) from error

        return data


class FliprHubDataUpdateCoordinator(BaseDataUpdateCoordinator[dict[str, Any]]):
    """Class to hold Flipr hub data retrieval."""

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API endpoint."""
        try:
            data = await self.hass.async_add_executor_job(
                self.client.get_hub_state, self.device_id
            )
        except FliprError as error:
            raise UpdateFailed(error) from error

        return data
