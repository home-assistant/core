"""Coordinator for Imeon integration."""

from __future__ import annotations

from asyncio import timeout
from datetime import timedelta
import logging
from typing import Any

from imeon_inverter_api.inverter import Inverter

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import TIMEOUT

HUBNAME = "imeon_inverter_hub"
INTERVAL = timedelta(seconds=60)
_LOGGER = logging.getLogger(__name__)

type InverterConfigEntry = ConfigEntry[InverterCoordinator]


# HUB CREATION #
class InverterCoordinator(DataUpdateCoordinator[dict[str, str | float | int]]):
    """Each inverter is it's own HUB, thus it's own data set.

    This allows this integration to handle as many
    inverters as possible in parallel.
    """

    config_entry: InverterConfigEntry

    # Implement methods to fetch and update data
    def __init__(
        self,
        hass: HomeAssistant,
        entry: InverterConfigEntry,
    ) -> None:
        """Initialize data update coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name=HUBNAME,
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=INTERVAL,
            always_update=True,
            config_entry=entry,
        )

        self._HUBs: dict[Any, InverterCoordinator] = {}
        self.api = Inverter(entry.data[CONF_ADDRESS])  # API calls

    async def _async_setup(self) -> None:
        """Set up the coordinator."""
        async with timeout(TIMEOUT * 2):
            if self.config_entry is not None:
                # Am I logged in ? If not log in
                await self.api.login(
                    self.config_entry.data[CONF_USERNAME],
                    self.config_entry.data[CONF_PASSWORD],
                )

                await self.api.init()

    async def _async_update_data(self) -> dict[str, str | float | int]:
        """Fetch and store newest data from API.

        This is the place to where entities can get their data.
        It also includes the login process.
        """

        data: dict[str, str | float | int] = {}

        async with timeout(TIMEOUT * 4):
            # Am I logged in ? If not log in
            await self.api.login(
                self.config_entry.data[CONF_USERNAME],
                self.config_entry.data[CONF_PASSWORD],
            )

            # Fetch data using distant API
            await self.api.update()

        # Store data
        for key, val in self.api.storage.items():
            if key == "timeline":
                data[key] = val
            else:
                for sub_key, sub_val in val.items():
                    data[f"{key}_{sub_key}"] = sub_val

        return data  # send stored data so entities can poll it
