"""Helper methods for common PlayStation Network integration operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import partial
from typing import Any

from psnawp_api import PSNAWP
from psnawp_api.models.client import Client
from psnawp_api.models.trophies import PlatformType, TrophySummary
from psnawp_api.models.user import User
from pyrate_limiter import Duration, Rate

from homeassistant.core import HomeAssistant

from .const import SUPPORTED_PLATFORMS

LEGACY_PLATFORMS = {PlatformType.PS3, PlatformType.PS4}


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
    available: bool = False
    active_sessions: dict[PlatformType, SessionData] = field(default_factory=dict)
    registered_platforms: set[PlatformType] = field(default_factory=set)
    trophy_summary: TrophySummary | None = None
    profile: dict[str, Any] = field(default_factory=dict)


class PlaystationNetwork:
    """Helper Class to return playstation network data in an easy to use structure."""

    def __init__(self, hass: HomeAssistant, npsso: str) -> None:
        """Initialize the class with the npsso token."""
        rate = Rate(300, Duration.MINUTE * 15)
        self.psn = PSNAWP(npsso, rate_limit=rate)
        self.client: Client | None = None
        self.hass = hass
        self.user: User
        self.legacy_profile: dict[str, Any] | None = None

    async def get_user(self) -> User:
        """Get the user object from the PlayStation Network."""
        self.user = await self.hass.async_add_executor_job(
            partial(self.psn.user, online_id="me")
        )
        return self.user

    def retrieve_psn_data(self) -> PlaystationNetworkData:
        """Bundle api calls to retrieve data from the PlayStation Network."""
        data = PlaystationNetworkData()

        if not self.client:
            self.client = self.psn.me()

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

        data.available = (
            data.presence.get("basicPresence", {}).get("availability")
            == "availableToPlay"
        )

        session = SessionData()
        session.platform = PlatformType(
            data.presence["basicPresence"]["primaryPlatformInfo"]["platform"]
        )

        if session.platform in SUPPORTED_PLATFORMS:
            session.status = data.presence.get("basicPresence", {}).get(
                "primaryPlatformInfo"
            )["onlineStatus"]

            game_title_info = data.presence.get("basicPresence", {}).get(
                "gameTitleInfoList"
            )

            if game_title_info:
                session.title_id = game_title_info[0]["npTitleId"]
                session.title_name = game_title_info[0]["titleName"]
                session.format = PlatformType(game_title_info[0]["format"])
                if session.format in {PlatformType.PS5, PlatformType.PSPC}:
                    session.media_image_url = game_title_info[0]["conceptIconUrl"]
                else:
                    session.media_image_url = game_title_info[0]["npTitleIconUrl"]

            data.active_sessions[session.platform] = session

        if self.legacy_profile:
            presence = self.legacy_profile["profile"].get("presences", [])
            if (game_title_info := presence[0] if presence else {}) and game_title_info[
                "onlineStatus"
            ] == "online":
                data.available = True

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
