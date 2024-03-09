"""Data update coordinator for the Steam integration."""

from __future__ import annotations

from datetime import timedelta

import steam
from steam.api import _interface_method as INTMethod

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_ACCOUNTS, DOMAIN, LOGGER


class SteamDataUpdateCoordinator(
    DataUpdateCoordinator[dict[str, dict[str, str | int]]]
):
    """Data update coordinator for the Steam integration."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )
        self.game_icons: dict[int, str] = {}
        self.player_interface: INTMethod = None
        self.user_interface: INTMethod = None
        steam.api.key.set(self.config_entry.data[CONF_API_KEY])

    def _update(self) -> dict[str, dict[str, str | int]]:
        """Fetch data from API endpoint."""
        accounts = self.config_entry.options[CONF_ACCOUNTS]
        _ids = list(accounts)
        if not self.user_interface or not self.player_interface:
            self.user_interface = steam.api.interface("ISteamUser")
            self.player_interface = steam.api.interface("IPlayerService")
        if not self.game_icons:
            for _id in _ids:
                res = self.player_interface.GetOwnedGames(
                    steamid=_id, include_appinfo=1
                )["response"]
                self.game_icons = self.game_icons | {
                    game["appid"]: game["img_icon_url"] for game in res.get("games", [])
                }
        response = self.user_interface.GetPlayerSummaries(steamids=_ids)
        players = {
            player["steamid"]: player
            for player in response["response"]["players"]["player"]
            if player["steamid"] in _ids
        }
        for k in players:
            data = self.player_interface.GetSteamLevel(steamid=players[k]["steamid"])
            players[k]["level"] = data["response"].get("player_level")
        return players

    async def _async_update_data(self) -> dict[str, dict[str, str | int]]:
        """Send request to the executor."""
        try:
            return await self.hass.async_add_executor_job(self._update)

        except (steam.api.HTTPError, steam.api.HTTPTimeoutError) as ex:
            if "401" in str(ex):
                raise ConfigEntryAuthFailed from ex
            raise UpdateFailed(ex) from ex
