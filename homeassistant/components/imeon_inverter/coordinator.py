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
_LOGGER = logging.getLogger(__name__)

type InverterConfigEntry = ConfigEntry[InverterCoordinator]


# HUB CREATION #
class InverterCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Abstract representation of an inverter.

    A HUB or a data update coordinator is a HASS Object that automatically polls
    data at regular intervals. Entities representing the different sensors and
    settings then all poll data from their HUB. Each inverter is it's own HUB
    thus it's own data set. This allows this integration to handle as many
    inverters as possible in parallel.
    """

    _HUBs: dict[Any, InverterCoordinator] = {}

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

        # Store request data
        self.data = {}

    def update(self, entry: InverterConfigEntry) -> None:
        """Update HUB data based on user input."""
        self.api = Inverter(entry.data[CONF_ADDRESS])

    def store_data(self, entity_dict):
        """Store in data for entities to use."""
        for key in entity_dict:
            if key != "timeline":
                val = entity_dict[key]
                for sub_key, sub_val in val.items():
                    self.data[key + "_" + sub_key] = sub_val
            else:  # Timeline is a list not a dict
                self.data[key] = entity_dict[key]

    async def init_and_store(self) -> dict[str, Any]:
        """Init API and store the data provided."""
        await self.api.init()
        self.store_data(self.api.storage)
        return self.data

    async def _async_setup(self) -> None:
        """Set up the coordinator."""
        try:
            async with timeout(TIMEOUT):
                if self.config_entry is not None:
                    # Am I logged in ? If not log in
                    await self.api.login(
                        self.config_entry.data[CONF_USERNAME],
                        self.config_entry.data[CONF_PASSWORD],
                    )

                    self.hass.async_create_task(self.init_and_store())

        except TimeoutError:
            _LOGGER.error(
                "Timeout Error: Reconnection failed, please check credentials. If the error persists check the network connection"
            )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch and store newest data from API.

        This is the place to where entities can get their data.
        It also includes the login process.
        """

        try:
            if self.config_entry is not None:
                async with timeout(TIMEOUT * 4):
                    # Am I logged in ? If not log in
                    await self.api.login(
                        self.config_entry.data[CONF_USERNAME],
                        self.config_entry.data[CONF_PASSWORD],
                    )

                    # Fetch data using distant API
                    await self.api.update()

        except TimeoutError:
            _LOGGER.error(
                "Timeout Error: Reconnection failed, please check credentials. If the error persists check the network connection"
            )

        # Store in data for entities to use
        self.store_data(self.api.storage)

        return self.data  # send stored data so entities can poll it
