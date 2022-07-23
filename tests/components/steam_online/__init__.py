"""Tests for Steam integration."""
from unittest.mock import patch

from homeassistant.components.steam_online import DOMAIN
from homeassistant.components.steam_online.const import CONF_ACCOUNT, CONF_ACCOUNTS
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

API_KEY = "abc123"
ACCOUNT_1 = "12345678901234567"
ACCOUNT_2 = "12345678901234568"
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


def create_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Add config entry in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF_DATA,
        options=CONF_OPTIONS_2,
        unique_id=ACCOUNT_1,
    )
    entry.add_to_hass(hass)
    return entry


class MockedInterface(dict):
    """Mocked interface."""

    def IPlayerService(self) -> None:
        """Mock iplayerservice."""

    def ISteamUser(self) -> None:
        """Mock iSteamUser."""

    def GetFriendList(self, steamid: str, relationship="all") -> dict:
        """Get friend list."""
        return {
            "friendslist": {
                "friends": [
                    {
                        "steamid": ACCOUNT_2,
                        "relationship": "friend",
                        "friend_since": 1359962692,
                    }
                ]
            }
        }

    def GetPlayerSummaries(self, version=2, steamids="") -> dict:
        """Get player summaries."""
        return {
            "response": {
                "players": [
                    {
                        "steamid": ACCOUNT_1,
                        "communityvisibilitystate": 3,
                        "profilestate": 1,
                        "personaname": ACCOUNT_NAME_1,
                        "commentpermission": 1,
                        "profileurl": "https://steamcommunity.com/id/testaccount1/",
                        "avatar": "https://avatars.akamai.steamstatic.com/0123456789012345678901234567890123456789.jpg",
                        "avatarmedium": "https://avatars.akamai.steamstatic.com/0123456789012345678901234567890123456789_medium.jpg",
                        "avatarfull": "https://avatars.akamai.steamstatic.com/0123456789012345678901234567890123456789_full.jpg",
                        "avatarhash": "0123456789012345678901234567890123456789",
                        "lastlogoff": 1608417705,
                        "personastate": 3,
                        "realname": "Test 1",
                        "primaryclanid": "012345678901234567",
                        "timecreated": 1330919730,
                        "personastateflags": 0,
                        "gameextrainfo": "Test Game",
                        "gameid": "1",
                        "loccountrycode": "US",
                    },
                    {
                        "steamid": ACCOUNT_2,
                        "communityvisibilitystate": 3,
                        "profilestate": 1,
                        "personaname": ACCOUNT_NAME_2,
                        "commentpermission": 1,
                        "profileurl": "https://steamcommunity.com/id/testaccount2/",
                        "avatar": "https://avatars.akamai.steamstatic.com/0123456789012345678901234567890123456780.jpg",
                        "avatarmedium": "https://avatars.akamai.steamstatic.com/0123456789012345678901234567890123456780_medium.jpg",
                        "avatarfull": "https://avatars.akamai.steamstatic.com/0123456789012345678901234567890123456780_full.jpg",
                        "avatarhash": "0123456789012345678901234567890123456780",
                        "lastlogoff": 1600417705,
                        "personastate": 3,
                        "realname": "Test 1",
                        "primaryclanid": "012345678901234568",
                        "timecreated": 1331819730,
                        "personastateflags": 0,
                        "gameextrainfo": "Test Game 2",
                        "gameid": "2",
                        "loccountrycode": "US",
                    },
                ]
            }
        }

    def GetOwnedGames(self, steamid: str, include_appinfo: int) -> dict:
        """Get owned games."""
        return {
            "response": {
                "game_count": 2,
                "games": [
                    {
                        "appid": 1,
                        "name": "Test App 1",
                        "playtime_forever": 0,
                        "img_icon_url": "0123456789012345678901234567890123456789",
                        "has_community_visible_stats": True,
                        "playtime_windows_forever": 0,
                        "playtime_mac_forever": 0,
                        "playtime_linux_forever": 0,
                    },
                    {
                        "appid": 2,
                        "name": "Test App 2",
                        "playtime_forever": 0,
                        "img_icon_url": "0123456789012345678901234567890123456780",
                        "has_community_visible_stats": True,
                        "playtime_windows_forever": 0,
                        "playtime_mac_forever": 0,
                        "playtime_linux_forever": 0,
                    },
                ],
            },
        }

    def GetSteamLevel(self, steamid: str) -> dict:
        """Get steam level."""
        return {"response": {"player_level": 10}}


def patch_interface() -> MockedInterface:
    """Patch interface."""
    return patch("steam.api.interface", return_value=MockedInterface())


def patch_coordinator_interface() -> MockedInterface:
    """Patch coordinator interface."""
    return patch(
        "homeassistant.components.steam_online.coordinator.interface",
        return_value=MockedInterface(),
    )
