"""Tests for Steam integration."""

import random
import string
from unittest.mock import patch
import urllib.parse

import steam

from homeassistant.components.steam_online.const import (
    CONF_ACCOUNT,
    CONF_ACCOUNTS,
    DOMAIN,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

API_KEY = "abc123"
ACCOUNT_1 = "12345678901234567"
ACCOUNT_2 = "12345678912345678"
ACCOUNT_NAME_1 = "testaccount1"
ACCOUNT_NAME_2 = "testaccount2"

CONF_DATA = {
    CONF_API_KEY: API_KEY,
    CONF_ACCOUNT: ACCOUNT_1,
}

CONF_OPTIONS = {CONF_ACCOUNTS: {ACCOUNT_1: ACCOUNT_NAME_1}}

CONF_OPTIONS_2 = {
    CONF_ACCOUNTS: {
        ACCOUNT_1: ACCOUNT_NAME_1,
        ACCOUNT_2: ACCOUNT_NAME_2,
    }
}

MAX_LENGTH_STEAM_IDS = 30


def create_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Add config entry in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF_DATA,
        options=CONF_OPTIONS,
        unique_id=ACCOUNT_1,
    )
    entry.add_to_hass(hass)
    return entry


class MockedUserInterfaceNull:
    """Mocked user interface returning no players."""

    def GetPlayerSummaries(self, steamids: str) -> dict:
        """Get player summaries."""
        return {"response": {"players": {"player": [None]}}}


class MockedInterface(dict):
    """Mocked interface."""

    def IPlayerService(self) -> None:
        """Mock iplayerservice."""

    def ISteamUser(self) -> None:
        """Mock iSteamUser."""

    def GetFriendList(self, steamid: str) -> dict:
        """Get friend list."""
        fake_friends = [{"steamid": ACCOUNT_2}]
        fake_friends.extend(
            {"steamid": "".join(random.choices(string.digits, k=len(ACCOUNT_1)))}
            for _ in range(4)
        )
        return {"friendslist": {"friends": fake_friends}}

    def GetPlayerSummaries(self, steamids: str | list[str]) -> dict:
        """Get player summaries."""
        assert len(urllib.parse.quote(str(steamids))) <= MAX_LENGTH_STEAM_IDS
        return {
            "response": {
                "players": {
                    "player": [
                        {
                            "steamid": ACCOUNT_1,
                            "personaname": ACCOUNT_NAME_1,
                            "personastate": 1,
                            "avatarmedium": "",
                        },
                        {
                            "steamid": ACCOUNT_2,
                            "personaname": ACCOUNT_NAME_2,
                            "personastate": 2,
                            "avatarmedium": "",
                        },
                    ]
                }
            }
        }

    def GetOwnedGames(self, steamid: str, include_appinfo: int) -> dict:
        """Get owned games."""
        return {
            "response": {"game_count": 1},
            "games": [{"appid": 1, "img_icon_url": "1234567890"}],
        }

    def GetSteamLevel(self, steamid: str) -> dict:
        """Get steam level."""
        return {"response": {"player_level": 10}}


class MockedInterfacePrivate(MockedInterface):
    """Mocked interface for private friends list."""

    def GetFriendList(self, steamid: str) -> None:
        """Get friend list."""
        raise steam.api.HTTPError


def patch_interface() -> MockedInterface:
    """Patch interface."""
    return patch("steam.api.interface", return_value=MockedInterface())


def patch_interface_private() -> MockedInterfacePrivate:
    """Patch interface for private friends list."""
    return patch("steam.api.interface", return_value=MockedInterfacePrivate())


def patch_user_interface_null() -> MockedUserInterfaceNull:
    """Patch player interface with no players."""
    return patch("steam.api.interface", return_value=MockedUserInterfaceNull())
