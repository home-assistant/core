"""Data update coordinator for Linea Research integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, NAME
from .tipi_client import TIPIClient, TIPIConnectionError, TIPIProtocolError

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=10)

type LineaResearchConfigEntry = ConfigEntry[LineaResearchDataUpdateCoordinator]


class LineaResearchDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Data update coordinator for Linea Research amplifiers."""

    config_entry: LineaResearchConfigEntry

    def __init__(
        self, 
        hass: HomeAssistant, 
        config_entry: LineaResearchConfigEntry,
        client: TIPIClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=NAME,
            update_interval=SCAN_INTERVAL,
            config_entry=config_entry,
        )
        
        self.client = client
        self.device_info: dict[str, Any] = {}

    async def async_setup(self) -> None:
        """Set up the coordinator."""
        try:
            await self.client.connect()
            self.device_info = await self.client.get_device_info()
            _LOGGER.debug("Device info: %s", self.device_info)
        except TIPIConnectionError as err:
            raise ConfigEntryNotReady(
                f"Unable to connect to {self.config_entry.data[CONF_HOST]}"
            ) from err

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the amplifier."""
        try:
            if not self.client._connected:
                await self.client.connect()
                
            status = await self.client.get_status()
            _LOGGER.debug("Status update: %s", status)
            return status
            
        except TIPIConnectionError as err:
            raise UpdateFailed(f"Failed to connect: {err}") from err
        except TIPIProtocolError as err:
            raise UpdateFailed(f"Protocol error: {err}") from err

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator."""
        await self.client.disconnect()