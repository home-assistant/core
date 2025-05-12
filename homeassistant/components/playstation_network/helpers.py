"""Helper methods for common PlayStation Network integration operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from psnawp_api import PSNAWP
from psnawp_api.core.psnawp_exceptions import PSNAWPNotFoundError
from psnawp_api.models.trophies import PlatformType as PSNAWPPlatformType
from psnawp_api.models.user import User

from .const import PlatformType

LEGACY_PLATFORMS = {PlatformType.PS3, PlatformType.PS4}
SUPPORTED_PLATFORMS = {PlatformType.PS3, PlatformType.PS4, PlatformType.PS5}


@dataclass
class SessionData:
    """Dataclass representing console session data."""

    platform: str | None = None
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
    active_sessions: list[SessionData] = field(default_factory=list)
    registered_platforms: set[str] = field(default_factory=set)


class PlaystationNetwork:
    """Helper Class to return playstation network data in an easy to use structure."""

    def __init__(self, npsso: str) -> None:
        """Initialize the class with the npsso token."""
        self.psn = PSNAWP(npsso)
        self.client = self.psn.me()
        self.user: User | None = None
        self.legacy_profile: dict[str, Any] | None = None

    def get_user(self) -> User:
        """Get the user object from the PlayStation Network."""
        self.user = self.psn.user(online_id="me")
        return self.user

    def get_data(self) -> PlaystationNetworkData:
        """Get title data from the PlayStation Network."""
        data = PlaystationNetworkData()

        if not self.user:
            self.user = self.get_user()

        data.registered_platforms = {
            device["deviceType"] for device in self.client.get_account_devices()
        } & {
            PlatformType.PS3,
            PlatformType.PS4,
            PlatformType.PS5,
        }

        data.username = self.user.online_id
        data.account_id = self.user.account_id
        data.presence = self.user.get_presence()

        data.available = (
            data.presence.get("basicPresence", {}).get("availability")
            == "availableToPlay"
        )

        session = SessionData()
        session.platform = data.presence["basicPresence"]["primaryPlatformInfo"][
            "platform"
        ]

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
                session.format = game_title_info[0]["format"]
                if session.format == PlatformType.PS5:
                    session.media_image_url = game_title_info[0]["conceptIconUrl"]
                else:
                    session.media_image_url = game_title_info[0]["npTitleIconUrl"]

            data.active_sessions.append(session)

        # check legacy platforms if owned
        if set(LEGACY_PLATFORMS).issubset(data.registered_platforms):
            self.legacy_profile = self.client.get_profile_legacy()
            presence = self.legacy_profile["profile"].get("presences", [])
            game_title_info = presence[0] if presence else {}
            session = SessionData()

            # If primary console isn't online, check legacy platforms for status
            if not data.available:
                data.available = game_title_info["onlineStatus"] == "online"

            if "npTitleId" in game_title_info:
                session.title_id = game_title_info["npTitleId"]
                session.title_name = game_title_info["titleName"]
                session.format = game_title_info["platform"]
                session.platform = game_title_info["platform"]
                session.status = game_title_info["onlineStatus"]
                if session.format == PlatformType.PS4:
                    session.media_image_url = game_title_info["npTitleIconUrl"]
                elif session.format == PlatformType.PS3:
                    try:
                        title = self.psn.game_title(session.title_id, "me")
                        session.media_image_url = title.get_title_icon_url(
                            PSNAWPPlatformType.PS3
                        )
                    except PSNAWPNotFoundError:
                        session.media_image_url = None

            if game_title_info["onlineStatus"] == "online":
                data.active_sessions.append(session)
        return data
