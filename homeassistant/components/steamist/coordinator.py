"""DataUpdateCoordinator for steamist."""

from __future__ import annotations

from datetime import timedelta
import logging

from aiosteamist import Steamist, SteamistStatus

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class SteamistDataUpdateCoordinator(DataUpdateCoordinator[SteamistStatus]):
    """DataUpdateCoordinator to gather data from a steamist steam shower."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        client: Steamist,
    ) -> None:
        """Initialize DataUpdateCoordinator to gather data for specific steamist."""
        self.client = client
        self.device_name = config_entry.data.get(CONF_NAME)  # Only found from discovery
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"Steamist {config_entry.data[CONF_HOST]}",
            update_interval=timedelta(seconds=5),
            always_update=False,
        )

    async def _async_update_data(self) -> SteamistStatus:
        """Fetch data from steamist."""
        return await self.client.async_get_status()
