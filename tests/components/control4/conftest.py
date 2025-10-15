"""Common fixtures for the Control4 tests."""

from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.control4.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry, load_fixture

MOCK_HOST = "192.168.1.100"
MOCK_USERNAME = "test-username"
MOCK_PASSWORD = "test-password"
MOCK_CONTROLLER_UNIQUE_ID = "control4_test_123"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_USERNAME: MOCK_USERNAME,
            CONF_PASSWORD: MOCK_PASSWORD,
            "controller_unique_id": MOCK_CONTROLLER_UNIQUE_ID,
        },
        unique_id="00:aa:00:aa:00:aa",
    )


@pytest.fixture
def mock_c4_account() -> Generator[MagicMock]:
    """Mock a Control4 Account client."""
    with patch(
        "homeassistant.components.control4.C4Account", autospec=True
    ) as mock_account_class:
        mock_account = mock_account_class.return_value
        mock_account.getAccountBearerToken = AsyncMock()
        mock_account.getAccountControllers = AsyncMock(
            return_value={"href": "https://example.com"}
        )
        mock_account.getDirectorBearerToken = AsyncMock(return_value={"token": "test"})
        mock_account.getControllerOSVersion = AsyncMock(return_value="3.2.0")
        yield mock_account


@pytest.fixture
def mock_c4_director() -> Generator[MagicMock]:
    """Mock a Control4 Director client."""
    with patch(
        "homeassistant.components.control4.C4Director", autospec=True
    ) as mock_director_class:
        mock_director = mock_director_class.return_value
        # Default: Multi-room setup (room with sources, room without sources)
        # Note: The API returns JSON strings, so we load fixtures as strings
        mock_director.getAllItemInfo = AsyncMock(
            return_value=load_fixture("director_all_items.json", DOMAIN)
        )
        mock_director.getUiConfiguration = AsyncMock(
            return_value=load_fixture("ui_configuration.json", DOMAIN)
        )
        yield mock_director


@pytest.fixture
def mock_update_variables() -> Generator[AsyncMock]:
    """Mock the update_variables_for_config_entry function."""

    async def _mock_update_variables(*args, **kwargs):
        return {
            1: {
                "POWER_STATE": True,
                "CURRENT_VOLUME": 50,
                "IS_MUTED": False,
                "CURRENT_VIDEO_DEVICE": 100,
                "CURRENT MEDIA INFO": {},
                "PLAYING": False,
                "PAUSED": False,
                "STOPPED": False,
            }
        }

    with patch(
        "homeassistant.components.control4.media_player.update_variables_for_config_entry",
        new=_mock_update_variables,
    ) as mock_update:
        yield mock_update


@pytest.fixture
def platforms() -> list[str]:
    """Platforms which should be loaded during the test."""
    return ["media_player"]


@pytest.fixture(autouse=True)
async def mock_patch_platforms(platforms: list[str]) -> AsyncGenerator[None]:
    """Fixture to set up platforms for tests."""
    with patch("homeassistant.components.control4.PLATFORMS", platforms):
        yield
