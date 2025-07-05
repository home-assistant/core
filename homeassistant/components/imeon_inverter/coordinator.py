"""Coordinator for Imeon integration."""

from __future__ import annotations

from asyncio import timeout
from datetime import timedelta
import logging

from aiohttp import ClientError
from imeon_inverter_api.inverter import Inverter

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

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
            name=HUBNAME,
            update_interval=INTERVAL,
            config_entry=entry,
        )

        self._api = Inverter(entry.data[CONF_HOST])

    @property
    def api(self) -> Inverter:
        """Return the inverter object."""
        return self._api

    async def _async_setup(self) -> None:
        """Set up the coordinator."""
        async with timeout(TIMEOUT):
            await self._api.login(
                self.config_entry.data[CONF_USERNAME],
                self.config_entry.data[CONF_PASSWORD],
            )

            await self._api.init()

    async def _async_update_data(self) -> dict[str, str | float | int]:
        """Fetch and store newest data from API.

        This is the place to where entities can get their data.
        It also includes the login process.
        """

        data: dict[str, str | float | int] = {}

        async with timeout(TIMEOUT):
            await self._api.login(
                self.config_entry.data[CONF_USERNAME],
                self.config_entry.data[CONF_PASSWORD],
            )

            # Fetch data using distant API
            try:
                await self._api.update()
            except (ValueError, ClientError) as e:
                raise UpdateFailed(e) from e

        # Store data
        for key, val in self._api.storage.items():
            if key == "timeline":
                data[key] = val
            else:
                for sub_key, sub_val in val.items():
                    data[f"{key}_{sub_key}"] = sub_val

        return data
