"""Data update coordinator for the Steam integration."""

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, override

import steam.api

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SUBENTRY_TYPE_FRIEND

type SteamConfigEntry = ConfigEntry[SteamDataUpdateCoordinator]

_LOGGER = logging.getLogger(__name__)


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
    lobbysteamid: str | None = None
    level: int | None = None


class SteamDataUpdateCoordinator(DataUpdateCoordinator[dict[str, PlayerData]]):
    """Data update coordinator for the Steam integration."""

    config_entry: SteamConfigEntry
    user_interface: steam.api.interface
    player_interface: steam.api.interface

    def __init__(self, hass: HomeAssistant, config_entry: SteamConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )
        self.game_icons: dict[str, str] = {}

    @override
    async def _async_setup(self) -> None:
        """Set up the coordinator."""

        steam.api.key.set(self.config_entry.data[CONF_API_KEY])
        self.user_interface = steam.api.interface("ISteamUser")
        self.player_interface = steam.api.interface("IPlayerService")

    def _update(self) -> dict[str, PlayerData]:
        """Fetch data from API endpoint."""
        if TYPE_CHECKING:
            assert self.config_entry.unique_id
        _ids = [self.config_entry.unique_id]
        _ids.extend(
            subentry.unique_id
            for subentry in self.config_entry.get_subentries_of_type(
                SUBENTRY_TYPE_FRIEND
            )
            if subentry.unique_id
        )

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
                games = self.player_interface.GetOwnedGames(
                    steamid=player.steamid,
                    include_appinfo=1,
                    include_played_free_games=True,
                )["response"].get("games", [])
                self.game_icons.update(
                    {str(game["appid"]): game["img_icon_url"] for game in games}
                )

        return players

    @override
    async def _async_update_data(self) -> dict[str, PlayerData]:
        """Send request to the executor."""
        try:
            return await self.hass.async_add_executor_job(self._update)

        except steam.api.HTTPTimeoutError as ex:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="timeout_exception",
            ) from ex
        except steam.api.HTTPError as ex:
            _LOGGER.debug("Full exception:", exc_info=True)
            if "401" in str(ex) or "403" in str(ex):
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="auth_exception",
                ) from ex
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="request_exception",
            ) from ex
