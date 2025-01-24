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
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import TIMEOUT

HUBNAME = "imeon_inverter_hub"
_LOGGER = logging.getLogger(__name__)

type InverterConfigEntry = ConfigEntry[InverterCoordinator]


# HUB CREATION #
class InverterCoordinator(DataUpdateCoordinator[dict[str, str | float | int]]):
    """Each inverter is it's own HUB, thus it's own data set.

    This allows this integration to handle as many
    inverters as possible in parallel.
    """

    _HUBs: dict[Any, InverterCoordinator] = {}
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
            update_interval=timedelta(minutes=1),
            always_update=True,
            config_entry=entry,
        )

        self.api = Inverter(entry.data[CONF_ADDRESS])  # API calls

    async def _async_setup(self) -> None:
        """Set up the coordinator."""
        try:
            async with timeout(TIMEOUT * 2):
                if self.config_entry is not None:
                    # Am I logged in ? If not log in
                    await self.api.login(
                        self.config_entry.data[CONF_USERNAME],
                        self.config_entry.data[CONF_PASSWORD],
                    )

                    await self.api.init()

        except TimeoutError as e:
            raise UpdateFailed(
                "Connection failed, please check credentials. If the error persists check the network connection"
            ) from e

    async def _async_update_data(self) -> dict[str, str | float | int]:
        """Fetch and store newest data from API.

        This is the place to where entities can get their data.
        It also includes the login process.
        """

        data = {}

        try:
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
                    if key != "timeline":
                        val = self.api.storage[key]
                        for sub_key, sub_val in val.items():
                            data[key + "_" + sub_key] = sub_val
                    else:  # Timeline is a list of dict, not a dict
                        data[key] = self.api.storage[key]

        except TimeoutError as e:
            raise UpdateFailed(
                "Reconnection failed, please check credentials. If the error persists check the network connection"
            ) from e

        return data  # send stored data so entities can poll it
