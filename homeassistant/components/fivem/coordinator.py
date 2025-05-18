"""The FiveM update coordinator."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from fivem import FiveM, FiveMServerOfflineError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ATTR_PLAYERS_LIST,
    ATTR_RESOURCES_LIST,
    DOMAIN,
    NAME_PLAYERS_MAX,
    NAME_PLAYERS_ONLINE,
    NAME_RESOURCES,
    NAME_STATUS,
    SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

type FiveMConfigEntry = ConfigEntry[FiveMDataUpdateCoordinator]


class FiveMDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching FiveM data."""

    def __init__(self, hass: HomeAssistant, entry: FiveMConfigEntry) -> None:
        """Initialize server instance."""
        self.unique_id = entry.entry_id
        self.server = None
        self.version = None
        self.game_name: str | None = None

        self.host = entry.data[CONF_HOST]

        self._fivem = FiveM(self.host, entry.data[CONF_PORT])

        update_interval = timedelta(seconds=SCAN_INTERVAL)

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=update_interval,
        )

    async def initialize(self) -> None:
        """Initialize the FiveM server."""
        info = await self._fivem.get_info_raw()
        self.server = info["server"]
        self.version = info["version"]
        self.game_name = info["vars"]["gamename"]

    async def _async_update_data(self) -> dict[str, Any]:
        """Get server data from 3rd party library and update properties."""
        try:
            server = await self._fivem.get_server()
        except FiveMServerOfflineError as err:
            raise UpdateFailed from err

        players_list: list[str] = [player.name for player in server.players]
        players_list.sort()

        resources_list = server.resources
        resources_list.sort()

        return {
            NAME_PLAYERS_ONLINE: len(players_list),
            NAME_PLAYERS_MAX: server.max_players,
            NAME_RESOURCES: len(resources_list),
            NAME_STATUS: self.last_update_success,
            ATTR_PLAYERS_LIST: players_list,
            ATTR_RESOURCES_LIST: resources_list,
        }
