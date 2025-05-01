"""Helper methods for common PlayStation Network integration operations."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from psnawp_api import PSNAWP
from psnawp_api.models.user import User


@dataclass
class PlaystationNetworkData:
    """Dataclass representing data retrieved from the Playstation Network api."""

    presence: dict[str, Any]
    username: str
    account_id: str
    available: bool
    title_metadata: dict[str, Any]
    platform: dict[str, Any]
    registered_platforms: list[str]


class PlaystationNetwork:
    """Helper Class to return playstation network data in an easy to use structure."""

    def __init__(self, npsso: str) -> None:
        """Initialize the class with the npsso token."""
        self.psn = PSNAWP(npsso)
        self.client = self.psn.me()
        self.user: User | None = None
        self.data: PlaystationNetworkData | None = None

    def get_user(self) -> User:
        """Get the user object from the PlayStation Network."""
        self.user = self.psn.user(online_id="me")
        return self.user

    def get_data(self) -> PlaystationNetworkData:
        """Get title data from the PlayStation Network."""
        data: PlaystationNetworkData = PlaystationNetworkData(
            {}, "", "", False, {}, {}, []
        )

        if not self.user:
            self.user = self.get_user()

        devices = self.client.get_account_devices()
        for device in devices:
            if (
                device.get("deviceType") in ["PS5", "PS4"]
                and device.get("deviceType") not in data.registered_platforms
            ):
                data.registered_platforms.append(device.get("deviceType", ""))

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

        self.data = data
        return self.data

    @staticmethod
    def parse_npsso_token(user_input: str = "") -> str:
        """Accept a string from the user that may contain either a valid npsso token or a json string with key "npsso" and value of the npsso token.

        This function either succeeds at extracting the npsso token from the provided input
        (meaning a valid npsso json string was provided) or it returns the original input.
        """
        try:
            npsso_input = json.loads(user_input)
            return npsso_input["npsso"]
        except Exception:  # noqa: BLE001
            return user_input
