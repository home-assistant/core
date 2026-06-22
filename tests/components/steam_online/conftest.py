"""Common fixtures for the Steam integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.steam_online.const import DOMAIN

from . import (
    ACCOUNT_1,
    ACCOUNT_2,
    ACCOUNT_NAME_1,
    ACCOUNT_NAME_2,
    CONF_DATA,
    CONF_OPTIONS,
)

from tests.common import MockConfigEntry, patch


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Mock Steam configuration entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=CONF_DATA,
        options=CONF_OPTIONS,
        unique_id=ACCOUNT_1,
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.steam_online.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="steam_api")
def mock_steam_api() -> Generator[MagicMock]:
    """Mock Steam API."""

    with (
        patch(
            "homeassistant.components.steam_online.config_flow.steam.api.interface"
        ) as mock_client,
        patch("homeassistant.components.steam_online.config_flow.steam.api.key.set"),
        patch(
            "homeassistant.components.steam_online.config_flow.MAX_IDS_TO_REQUEST",
            return_value=2,
        ),
    ):
        client = MagicMock()
        mock_client.return_value = client

        client.GetFriendList.return_value = {
            "friendslist": {"friends": [{"steamid": ACCOUNT_2}]}
        }
        client.GetSteamLevel.return_value = {"response": {"player_level": 10}}
        client.GetOwnedGames.return_value = {
            "response": {"game_count": 1},
            "games": [
                {
                    "appid": 20900,
                    "img_icon_url": "746d1cd48fb2e57d579b05b6e9eccba95859e549",
                },
            ],
        }
        client.GetPlayerSummaries.return_value = {
            "response": {
                "players": {
                    "player": [
                        {
                            "steamid": ACCOUNT_1,
                            "communityvisibilitystate": 1,
                            "profilestate": 1,
                            "personaname": ACCOUNT_NAME_1,
                            "profileurl": "https://steamcommunity.com/profiles/123456789/",
                            "avatar": "https://avatars.steamstatic.com/fef49e7fa7e1997310d705b2a6158ff8dc1cdfeb.jpg",
                            "avatarmedium": "https://avatars.steamstatic.com/fef49e7fa7e1997310d705b2a6158ff8dc1cdfeb_medium.jpg",
                            "avatarfull": "https://avatars.steamstatic.com/fef49e7fa7e1997310d705b2a6158ff8dc1cdfeb_full.jpg",
                            "avatarhash": "fef49e7fa7e1997310d705b2a6158ff8dc1cdfeb",
                            "lastlogoff": 1775409487,
                            "personastate": 1,
                            "realname": "John Dough",
                            "personastateflags": 0,
                            "gameextrainfo": "The Witcher: Enhanced Edition",
                            "gameid": "20900",
                        },
                        {
                            "steamid": ACCOUNT_2,
                            "communityvisibilitystate": 1,
                            "profilestate": 1,
                            "personaname": ACCOUNT_NAME_2,
                            "profileurl": "https://steamcommunity.com/profiles/987654321/",
                            "avatar": "https://avatars.steamstatic.com/fef49e7fa7e1997310d705b2a6158ff8dc1cdfeb.jpg",
                            "avatarmedium": "https://avatars.steamstatic.com/fef49e7fa7e1997310d705b2a6158ff8dc1cdfeb_medium.jpg",
                            "avatarfull": "https://avatars.steamstatic.com/fef49e7fa7e1997310d705b2a6158ff8dc1cdfeb_full.jpg",
                            "avatarhash": "fef49e7fa7e1997310d705b2a6158ff8dc1cdfeb",
                            "lastlogoff": 1775409487,
                            "personastate": 2,
                            "personastateflags": 0,
                        },
                    ]
                }
            }
        }

        yield mock_client
