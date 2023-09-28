"""The Minecraft Server integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_NAME, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    MinecraftServer,
    MinecraftServerAddressError,
    MinecraftServerConnectionError,
    MinecraftServerData,
)

SCAN_INTERVAL = timedelta(seconds=60)

_LOGGER = logging.getLogger(__name__)


class MinecraftServerCoordinator(DataUpdateCoordinator[MinecraftServerData]):
    """Minecraft Server data update coordinator."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize coordinator instance."""
        config_data = config_entry.data
        self.unique_id = config_entry.entry_id
        self.server_type = config_data[CONF_TYPE]

        super().__init__(
            hass=hass,
            name=config_data[CONF_NAME],
            logger=_LOGGER,
            update_interval=SCAN_INTERVAL,
        )

        try:
            self._api = MinecraftServer(self.server_type, config_data[CONF_ADDRESS])
        except MinecraftServerAddressError as error:
            raise HomeAssistantError(
                f"Address in configuration entry is invalid (error: {error}), please remove this device and add it again"
            ) from error

        _LOGGER.debug(
            "%s server instance created with address '%s'",
            self.server_type,
            config_data[CONF_ADDRESS],
        )

    async def _async_update_data(self) -> MinecraftServerData:
        """Get updated data from the server."""
        try:
            return await self._api.async_get_data()
        except MinecraftServerConnectionError as error:
            raise UpdateFailed(error) from error
