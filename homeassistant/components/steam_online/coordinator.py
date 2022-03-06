"""Data update coordinator for the Steam integration."""
from __future__ import annotations

from datetime import timedelta
import functools as ft

import steam
from steam.api import _interface_method as INTMethod

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_ACCOUNTS, DOMAIN, LOGGER


class SteamDataUpdateCoordinator(DataUpdateCoordinator):
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
        self.game_icons: dict = {}
        self.player_interface: INTMethod = None
        self.user_interface: INTMethod = None
        steam.api.key.set(self.config_entry.data[CONF_API_KEY])

    async def _async_update_data(self) -> dict[str, dict[str, str | int]]:
        """Fetch data from API endpoint."""
        accounts = self.config_entry.options[CONF_ACCOUNTS]
        _ids = [k for k in accounts.keys() if accounts[k]["enabled"]]
        try:
            if not self.user_interface or not self.player_interface:
                self.user_interface = await self.hass.async_add_executor_job(
                    steam.api.interface, "ISteamUser"
                )
                self.player_interface = await self.hass.async_add_executor_job(
                    steam.api.interface, "IPlayerService"
                )
            if not self.game_icons:
                for _id in _ids:
                    res = await self.hass.async_add_executor_job(
                        ft.partial(
                            self.player_interface.GetOwnedGames,
                            steamid=_id,
                            include_appinfo=1,
                        )
                    )
                    res = await self.hass.async_add_executor_job(res.get, "response")
                    self.game_icons = self.game_icons | {
                        str(game["appid"]): game["img_icon_url"]
                        for game in res.get("games", {})
                    }
            response = await self.hass.async_add_executor_job(
                ft.partial(self.user_interface.GetPlayerSummaries, steamids=str(_ids))
            )
            players = {
                str(player["steamid"]): player
                for player in (
                    await self.hass.async_add_executor_job(response.get, "response")
                )["players"]["player"]
                if player["steamid"] in _ids
            }
            for k in players.keys():
                data = await self.hass.async_add_executor_job(
                    ft.partial(
                        self.player_interface.GetSteamLevel,
                        steamid=players[k]["steamid"],
                    )
                )
                data = await self.hass.async_add_executor_job(data.get, "response")
                players[k]["level"] = data.get("player_level")
            return players

        except (steam.api.HTTPError, steam.api.HTTPTimeoutError) as ex:
            if "401" in str(ex):
                raise ConfigEntryAuthFailed from ex
            raise UpdateFailed(ex) from ex
