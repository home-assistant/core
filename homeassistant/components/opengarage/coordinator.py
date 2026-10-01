"""The OpenGarage integration."""

from collections.abc import Awaitable, Callable
from datetime import timedelta
import logging
from typing import override

import aiohttp
import opengarage
from opengarage.errors import OpenGarageError
from opengarage.state import NormalizedState

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import update_coordinator
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


type OpenGarageConfigEntry = ConfigEntry[OpenGarageDataUpdateCoordinator]


class OpenGarageDataUpdateCoordinator(DataUpdateCoordinator[NormalizedState]):
    """Class to manage fetching Opengarage data."""

    config_entry: OpenGarageConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: OpenGarageConfigEntry,
        open_garage_connection: opengarage.OpenGarage,
    ) -> None:
        """Initialize global Opengarage data updater."""
        self.open_garage_connection = open_garage_connection

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=5),
        )

    @override
    async def _async_update_data(self) -> NormalizedState:
        """Fetch data."""
        try:
            data = await self.open_garage_connection.get_state()
        except OpenGarageError as err:
            raise update_coordinator.UpdateFailed(
                "Unable to connect to OpenGarage device"
            ) from err
        if not {"name", "mac", "fwv", "door"} <= data.raw.keys():
            raise update_coordinator.UpdateFailed(
                "Unable to connect to OpenGarage device"
            )
        return data

    async def async_command(
        self, command: Callable[[], Awaitable[int | None]], *, allow_noop: bool = False
    ) -> None:
        """Execute a public command and translate failures into action errors."""
        try:
            result = await command()
        except (OpenGarageError, aiohttp.ClientError, TimeoutError) as err:
            raise HomeAssistantError("Unable to control OpenGarage device") from err
        if result == 1 or (allow_noop and result is None):
            return
        if result == 2:
            raise HomeAssistantError("OpenGarage device key is incorrect")
        raise HomeAssistantError(f"OpenGarage command failed: {result}")
