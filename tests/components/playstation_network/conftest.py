"""Common fixtures for the Playstation Network tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from psnawp_api.models.trophies import TrophySet, TrophySummary
import pytest

from homeassistant.components.playstation_network.const import CONF_NPSSO, DOMAIN

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
            {
                "deviceId": "1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234",
                "deviceType": "PS5",
                "activationType": "PRIMARY",
                "activationDate": "2021-01-14T18:00:00.000Z",
                "accountDeviceVector": "abcdefghijklmnopqrstuv",
            }
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
