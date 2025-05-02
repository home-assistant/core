"""Common fixtures for the Playstation Network tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

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
        yield client


@pytest.fixture
def mock_psnawp_npsso(mock_user: MagicMock) -> Generator[MagicMock]:
    """Mock psnawp_api."""

    with patch(
        "psnawp_api.utils.misc.parse_npsso_token",
        autospec=True,
    ) as mock_parse_npsso_token:
        npsso = mock_parse_npsso_token.return_value
        npsso.parse_npsso_token.return_value = NPSSO_TOKEN

        yield npsso


@pytest.fixture
def mock_token() -> Generator[MagicMock]:
    """Mock token generator."""
    with patch("secrets.token_hex", return_value="123456789") as token:
        yield token
