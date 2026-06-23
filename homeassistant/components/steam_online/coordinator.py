"""Data update coordinator for the Steam integration."""

from dataclasses import dataclass
from datetime import timedelta
from typing import ClassVar, override

import steam.api

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_ACCOUNTS, DOMAIN, LOGGER

type SteamConfigEntry = ConfigEntry[SteamDataUpdateCoordinator]


@dataclass(kw_only=True, frozen=True)
class PlayerData:
    """Steam player data."""

    steamid: str
    communityvisibilitystate: int
    profilestate: int
    personaname: str
    commentpermission: int | None = None
    profileurl: str
    avatar: str
    avatarmedium: str
    avatarfull: str
    avatarhash: str
    lastlogoff: int
    personastate: int
    realname: str | None = None
    primaryclanid: str | None = None
    timecreated: int | None = None
    personastateflags: int
    loccountrycode: str | None = None
    locstatecode: str | None = None
    loccityid: int | None = None
    gameextrainfo: str | None = None
    gameid: str | None = None
    level: int | None = None


class SteamDataUpdateCoordinator(DataUpdateCoordinator[dict[str, PlayerData]]):
    """Data update coordinator for the Steam integration."""

    config_entry: SteamConfigEntry
    user_interface: steam.api.interface
    player_interface: steam.api.interface
    game_icons: ClassVar[dict[str, str]] = {}

    def __init__(self, hass: HomeAssistant, config_entry: SteamConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )

    @override
    async def _async_setup(self) -> None:
        """Set up the coordinator."""

        steam.api.key.set(self.config_entry.data[CONF_API_KEY])
        self.user_interface = steam.api.interface("ISteamUser")
        self.player_interface = steam.api.interface("IPlayerService")

    def _update(self) -> dict[str, PlayerData]:
        """Fetch data from API endpoint."""
        accounts = self.config_entry.options[CONF_ACCOUNTS]
        _ids = list(accounts)

        response = self.user_interface.GetPlayerSummaries(steamids=_ids)
        players = {
            player["steamid"]: PlayerData(
                **player,
                level=self.player_interface.GetSteamLevel(steamid=player["steamid"])[
                    "response"
                ].get("player_level"),
            )
            for player in response["response"]["players"]["player"]
            if player["steamid"] in _ids
        }

        for player in players.values():
            if player.gameid and player.gameid not in self.game_icons:
                res = self.player_interface.GetOwnedGames(
                    steamid=player.steamid, include_appinfo=1
                )["response"]
                self.game_icons.update(
                    {
                        str(game["appid"]): game["img_icon_url"]
                        for game in res.get("games", [])
                    }
                )

        return players

    @override
    async def _async_update_data(self) -> dict[str, PlayerData]:
        """Send request to the executor."""
        try:
            return await self.hass.async_add_executor_job(self._update)

        except steam.api.HTTPError as ex:
            if "401" in str(ex):
                raise ConfigEntryAuthFailed from ex
            raise UpdateFailed(ex) from ex
