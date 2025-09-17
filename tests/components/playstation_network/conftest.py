"""Common fixtures for the Playstation Network tests."""

from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from psnawp_api.models import User
from psnawp_api.models.group.group import Group
from psnawp_api.models.trophies import (
    PlatformType,
    TrophySet,
    TrophySummary,
    TrophyTitle,
)
import pytest

from homeassistant.components.playstation_network.const import CONF_NPSSO, DOMAIN
from homeassistant.config_entries import ConfigSubentryData

from tests.common import MockConfigEntry

NPSSO_TOKEN: str = "npsso-token"
NPSSO_TOKEN_INVALID_JSON: str = "{'npsso': 'npsso-token'"
PSN_ID: str = "my-psn-id"


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Mock PlayStation Network configuration entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="test-user",
        data={
            CONF_NPSSO: NPSSO_TOKEN,
        },
        unique_id=PSN_ID,
        subentries_data=[
            ConfigSubentryData(
                data={},
                subentry_id="ABCDEF",
                subentry_type="friend",
                title="PublicUniversalFriend",
                unique_id="fren-psn-id",
            )
        ],
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.playstation_network.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_user() -> Generator[MagicMock]:
    """Mock psnawp_api User object."""

    with patch(
        "homeassistant.components.playstation_network.helpers.User",
        autospec=True,
    ) as mock_client:
        client = mock_client.return_value

        client.account_id = PSN_ID
        client.online_id = "testuser"

        client.get_presence.return_value = {
            "basicPresence": {
                "availability": "availableToPlay",
                "primaryPlatformInfo": {"onlineStatus": "online", "platform": "PS5"},
                "gameTitleInfoList": [
                    {
                        "npTitleId": "PPSA07784_00",
                        "titleName": "STAR WARS Jedi: Survivor™",
                        "format": "PS5",
                        "launchPlatform": "PS5",
                        "conceptIconUrl": "https://image.api.playstation.com/vulcan/ap/rnd/202211/2222/l8QTN7ThQK3lRBHhB3nX1s7h.png",
                    }
                ],
                "lastAvailableDate": "2025-06-30T01:42:15.391Z",
            }
        }

        yield client


@pytest.fixture
def mock_psnawpapi(mock_user: MagicMock) -> Generator[MagicMock]:
    """Mock psnawp_api."""

    with patch(
        "homeassistant.components.playstation_network.helpers.PSNAWP",
        autospec=True,
    ) as mock_client:
        client = mock_client.return_value

        client.user.return_value = mock_user
        client.me.return_value.get_account_devices.return_value = [
            {"deviceType": "PSVITA"},
            {
                "deviceId": "1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234",
                "deviceType": "PS5",
                "activationType": "PRIMARY",
                "activationDate": "2021-01-14T18:00:00.000Z",
                "accountDeviceVector": "abcdefghijklmnopqrstuv",
            },
        ]
        client.me.return_value.trophy_summary.return_value = TrophySummary(
            PSN_ID, 1079, 19, 10, TrophySet(14450, 8722, 11754, 1398)
        )
        client.user.return_value.profile.return_value = {
            "onlineId": "testuser",
            "personalDetail": {
                "firstName": "Rick",
                "lastName": "Astley",
                "profilePictures": [
                    {
                        "size": "xl",
                        "url": "http://static-resource.np.community.playstation.net/avatar_xl/WWS_A/UP90001312L24_DD96EB6A4FF5FE883C09_XL.png",
                    }
                ],
            },
            "aboutMe": "Never Gonna Give You Up",
            "avatars": [
                {
                    "size": "xl",
                    "url": "http://static-resource.np.community.playstation.net/avatar_xl/WWS_A/UP90001312L24_DD96EB6A4FF5FE883C09_XL.png",
                }
            ],
            "languages": ["de-DE"],
            "isPlus": True,
            "isOfficiallyVerified": False,
            "isMe": True,
        }
        client.user.return_value.trophy_titles.return_value = [
            TrophyTitle(
                np_service_name="trophy",
                np_communication_id="NPWR03134_00",
                trophy_set_version="01.03",
                title_name="Assassin's Creed® III Liberation",
                title_detail="Assassin's Creed® III Liberation",
                title_icon_url="https://image.api.playstation.com/trophy/np/NPWR03134_00_0008206095F67FD3BB385E9E00A7C9CFE6F5A4AB96/5F87A6997DD23D1C4D4CC0D1F958ED79CB905331.PNG",
                title_platform=frozenset({PlatformType.PS_VITA}),
                has_trophy_groups=False,
                progress=28,
                hidden_flag=False,
                earned_trophies=TrophySet(bronze=4, silver=8, gold=0, platinum=0),
                defined_trophies=TrophySet(bronze=22, silver=21, gold=1, platinum=1),
                last_updated_datetime=datetime(2016, 10, 6, 18, 5, 8, tzinfo=UTC),
                np_title_id=None,
            )
        ]
        client.me.return_value.get_profile_legacy.return_value = {
            "profile": {
                "presences": [
                    {
                        "onlineStatus": "online",
                        "platform": "PSVITA",
                        "npTitleId": "PCSB00074_00",
                        "titleName": "Assassin's Creed® III Liberation",
                        "hasBroadcastData": False,
                    }
                ]
            }
        }
        client.me.return_value.get_shareable_profile_link.return_value = {
            "shareImageUrl": "https://xxxxx.cloudfront.net/profile-testuser?Expires=1753304493"
        }
        group = MagicMock(spec=Group, group_id="test-groupid")

        group.get_group_information.return_value = {
            "groupName": {"value": ""},
            "members": [
                {"onlineId": "PublicUniversalFriend", "accountId": "fren-psn-id"},
                {"onlineId": "testuser", "accountId": PSN_ID},
            ],
        }
        client.me.return_value.get_groups.return_value = [group]
        fren = MagicMock(
            spec=User, account_id="fren-psn-id", online_id="PublicUniversalFriend"
        )
        fren.get_presence.return_value = mock_user.get_presence.return_value

        client.user.return_value.friends_list.return_value = [fren]

        yield client


@pytest.fixture
def mock_psnawp_npsso(mock_user: MagicMock) -> Generator[MagicMock]:
    """Mock psnawp_api."""

    with patch(
        "homeassistant.components.playstation_network.config_flow.parse_npsso_token",
        side_effect=lambda token: token,
    ) as npsso:
        yield npsso


@pytest.fixture
def mock_token() -> Generator[MagicMock]:
    """Mock token generator."""
    with patch("secrets.token_hex", return_value="123456789") as token:
        yield token
