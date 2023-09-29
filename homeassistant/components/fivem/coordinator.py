"""The FiveM update coordinator."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
import logging
from typing import Any

from fivem import FiveM, FiveMServerOfflineError

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

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


class FiveMDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching FiveM data."""

    def __init__(
        self, hass: HomeAssistant, config_data: Mapping[str, Any], unique_id: str
    ) -> None:
        """Initialize server instance."""
        self.unique_id = unique_id
        self.server = None
        self.version = None
        self.game_name: str | None = None

        self.host = config_data[CONF_HOST]

        self._fivem = FiveM(self.host, config_data[CONF_PORT])

        update_interval = timedelta(seconds=SCAN_INTERVAL)

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval)

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

        players_list: list[str] = []
        for player in server.players:
            players_list.append(player.name)
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
