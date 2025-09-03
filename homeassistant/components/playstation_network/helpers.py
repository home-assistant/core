"""Helper methods for common PlayStation Network integration operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import partial
from typing import Any

from psnawp_api import PSNAWP
from psnawp_api.models.client import Client
from psnawp_api.models.trophies import PlatformType, TrophySummary, TrophyTitle
from psnawp_api.models.user import User
from pyrate_limiter import Duration, Rate

from homeassistant.core import HomeAssistant

from .const import SUPPORTED_PLATFORMS

LEGACY_PLATFORMS = {PlatformType.PS3, PlatformType.PS4, PlatformType.PS_VITA}


@dataclass
class SessionData:
    """Dataclass representing console session data."""

    platform: PlatformType = PlatformType.UNKNOWN
    title_id: str | None = None
    title_name: str | None = None
    format: PlatformType | None = None
    media_image_url: str | None = None
    status: str = ""


@dataclass
class PlaystationNetworkData:
    """Dataclass representing data retrieved from the Playstation Network api."""

    presence: dict[str, Any] = field(default_factory=dict)
    username: str = ""
    account_id: str = ""
    active_sessions: dict[PlatformType, SessionData] = field(default_factory=dict)
    registered_platforms: set[PlatformType] = field(default_factory=set)
    trophy_summary: TrophySummary | None = None
    profile: dict[str, Any] = field(default_factory=dict)
    shareable_profile_link: dict[str, str] = field(default_factory=dict)


class PlaystationNetwork:
    """Helper Class to return playstation network data in an easy to use structure."""

    shareable_profile_link: dict[str, str]

    def __init__(self, hass: HomeAssistant, npsso: str) -> None:
        """Initialize the class with the npsso token."""
        rate = Rate(300, Duration.MINUTE * 15)
        self.psn = PSNAWP(npsso, rate_limit=rate)
        self.client: Client
        self.hass = hass
        self.user: User
        self.legacy_profile: dict[str, Any] | None = None
        self.trophy_titles: list[TrophyTitle] = []
        self._title_icon_urls: dict[str, str] = {}
        self.friends_list: dict[str, User] = {}

    def _setup(self) -> None:
        """Setup PSN."""
        self.user = self.psn.user(online_id="me")
        self.client = self.psn.me()
        self.shareable_profile_link = self.client.get_shareable_profile_link()
        self.trophy_titles = list(self.user.trophy_titles(page_size=500))
        self.friends_list = {
            friend.account_id: friend for friend in self.user.friends_list()
        }

    async def async_setup(self) -> None:
        """Setup PSN."""
        await self.hass.async_add_executor_job(self._setup)

    async def get_user(self) -> User:
        """Get the user object from the PlayStation Network."""
        self.user = await self.hass.async_add_executor_job(
            partial(self.psn.user, online_id="me")
        )
        return self.user

    def retrieve_psn_data(self) -> PlaystationNetworkData:
        """Bundle api calls to retrieve data from the PlayStation Network."""
        data = PlaystationNetworkData()

        data.registered_platforms = {
            PlatformType(device["deviceType"])
            for device in self.client.get_account_devices()
        } & SUPPORTED_PLATFORMS

        data.presence = self.user.get_presence()

        data.trophy_summary = self.client.trophy_summary()
        data.profile = self.user.profile()

        # check legacy platforms if owned
        if LEGACY_PLATFORMS & data.registered_platforms:
            self.legacy_profile = self.client.get_profile_legacy()

        return data

    async def get_data(self) -> PlaystationNetworkData:
        """Get title data from the PlayStation Network."""
        data = await self.hass.async_add_executor_job(self.retrieve_psn_data)
        data.username = self.user.online_id
        data.account_id = self.user.account_id
        data.shareable_profile_link = self.shareable_profile_link

        if "platform" in data.presence["basicPresence"]["primaryPlatformInfo"]:
            primary_platform = PlatformType(
                data.presence["basicPresence"]["primaryPlatformInfo"]["platform"]
            )
            game_title_info: dict[str, Any] = next(
                iter(
                    data.presence.get("basicPresence", {}).get("gameTitleInfoList", [])
                ),
                {},
            )
            status = data.presence.get("basicPresence", {}).get("primaryPlatformInfo")[
                "onlineStatus"
            ]
            title_format = (
                PlatformType(fmt) if (fmt := game_title_info.get("format")) else None
            )

            data.active_sessions[primary_platform] = SessionData(
                platform=primary_platform,
                status=status,
                title_id=game_title_info.get("npTitleId"),
                title_name=game_title_info.get("titleName"),
                format=title_format,
                media_image_url=(
                    game_title_info.get("conceptIconUrl")
                    or game_title_info.get("npTitleIconUrl")
                ),
            )

        if self.legacy_profile:
            presence = self.legacy_profile["profile"].get("presences", [])
            if (game_title_info := presence[0] if presence else {}) and game_title_info[
                "onlineStatus"
            ] != "offline":
                platform = PlatformType(game_title_info["platform"])

                if platform is PlatformType.PS4:
                    media_image_url = game_title_info.get("npTitleIconUrl")
                elif platform is PlatformType.PS3 and game_title_info.get("npTitleId"):
                    media_image_url = self.psn.game_title(
                        game_title_info["npTitleId"],
                        platform=PlatformType.PS3,
                        account_id="me",
                        np_communication_id="",
                    ).get_title_icon_url()
                elif platform is PlatformType.PS_VITA and game_title_info.get(
                    "npTitleId"
                ):
                    media_image_url = self.get_psvita_title_icon_url(game_title_info)
                else:
                    media_image_url = None

                data.active_sessions[platform] = SessionData(
                    platform=platform,
                    title_id=game_title_info.get("npTitleId"),
                    title_name=game_title_info.get("titleName"),
                    format=platform,
                    media_image_url=media_image_url,
                    status=game_title_info["onlineStatus"],
                )
        return data

    def get_psvita_title_icon_url(self, game_title_info: dict[str, Any]) -> str | None:
        """Look up title_icon_url from trophy titles data."""

        if url := self._title_icon_urls.get(game_title_info["npTitleId"]):
            return url

        url = next(
            (
                title.title_icon_url
                for title in self.trophy_titles
                if game_title_info["titleName"]
                == normalize_title(title.title_name or "")
                and next(iter(title.title_platform)) == PlatformType.PS_VITA
            ),
            None,
        )
        if url is not None:
            self._title_icon_urls[game_title_info["npTitleId"]] = url
        return url


def normalize_title(name: str) -> str:
    """Normalize trophy title."""
    return name.removesuffix("Trophies").removesuffix("Trophy Set").strip()


def get_game_title_info(presence: dict[str, Any]) -> dict[str, Any]:
    """Retrieve title info from presence."""

    return (
        next((title for title in game_title_info), {})
        if (
            game_title_info := presence.get("basicPresence", {}).get(
                "gameTitleInfoList"
            )
        )
        else {}
    )
