"""The Minecraft Server integration."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from mcstatus.server import JavaServer

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

SCAN_INTERVAL = timedelta(seconds=60)

_LOGGER = logging.getLogger(__name__)


@dataclass
class MinecraftServerData:
    """Representation of Minecraft Server data."""

    latency: float
    motd: str
    players_max: int
    players_online: int
    players_list: list[str]
    protocol_version: int
    version: str


class MinecraftServerCoordinator(DataUpdateCoordinator[MinecraftServerData]):
    """Minecraft Server data update coordinator."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize coordinator instance."""
        config_data = config_entry.data
        self.unique_id = config_entry.entry_id

        super().__init__(
            hass=hass,
            name=config_data[CONF_NAME],
            logger=_LOGGER,
            update_interval=SCAN_INTERVAL,
        )

        try:
            self._server = JavaServer.lookup(config_data[CONF_ADDRESS])
        except ValueError as error:
            raise HomeAssistantError(
                f"Address in configuration entry cannot be parsed (error: {error}), please remove this device and add it again"
            ) from error

    async def _async_update_data(self) -> MinecraftServerData:
        """Get server data from 3rd party library and update properties."""
        try:
            status_response = await self._server.async_status()
        except OSError as error:
            raise UpdateFailed(error) from error

        players_list = []
        if players := status_response.players.sample:
            for player in players:
                players_list.append(player.name)
            players_list.sort()

        return MinecraftServerData(
            version=status_response.version.name,
            protocol_version=status_response.version.protocol,
            players_online=status_response.players.online,
            players_max=status_response.players.max,
            players_list=players_list,
            latency=status_response.latency,
            motd=status_response.motd.to_plain(),
        )
