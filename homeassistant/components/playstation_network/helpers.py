"""Helper methods for common PlayStation Network integration operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from psnawp_api import PSNAWP
from psnawp_api.models.trophies import PlatformType as PSNAWPPlatformType
from psnawp_api.models.user import User

from .const import PlatformType


@dataclass
class PlaystationNetworkData:
    """Dataclass representing data retrieved from the Playstation Network api."""

    presence: dict[str, Any] = field(default_factory=dict)
    username: str = ""
    account_id: str = ""
    available: bool = False
    title_metadata: dict[str, Any] = field(default_factory=dict)
    platform: dict[str, Any] = field(default_factory=dict)
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
        data.platform = data.presence.get("basicPresence", {}).get(
            "primaryPlatformInfo"
        )

        game_title_info_list = data.presence.get("basicPresence", {}).get(
            "gameTitleInfoList"
        )

        if game_title_info_list:
            data.title_metadata = game_title_info_list[0]
            data.title_metadata["format"] = data.title_metadata["format"].upper()

        if (
            not data.available
        ):  # if user isn't showing as available, check legacy platforms if owned
            if PlatformType.PS3 in data.registered_platforms:
                self.legacy_profile = self.client.get_profile_legacy()
                presence = self.legacy_profile["profile"].get("presences", [])
                data.platform = presence[0] if presence else {}
                data.available = data.platform["onlineStatus"] == "online"
                if "npTitleId" in data.platform:
                    data.title_metadata = {
                        "npTitleId": data.platform["npTitleId"],
                        "titleName": data.platform["titleName"],
                        "format": data.platform["platform"],
                        "npTitleIconUrl": self.user.trophy_groups_summary(
                            np_communication_id=data.platform["npTitleId"],
                            platform=PlatformType.PS3,
                        ).trophy_title_icon_url,
                    }
        return data
