"""Common fixtures for the Steam integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.steam_online.const import DOMAIN

from . import ACCOUNT_1, CONF_DATA, CONF_OPTIONS

from tests.common import MockConfigEntry, load_json_object_fixture, patch


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
            "homeassistant.components.steam_online.config_flow.MAX_IDS_TO_REQUEST", 2
        ),
    ):
        client = MagicMock()
        mock_client.return_value = client

        client.GetFriendList.return_value = load_json_object_fixture(
            "GetFriendList.json", DOMAIN
        )
        client.GetSteamLevel.return_value = load_json_object_fixture(
            "GetSteamLevel.json", DOMAIN
        )
        client.GetOwnedGames.return_value = load_json_object_fixture(
            "GetOwnedGames.json", DOMAIN
        )
        client.GetPlayerSummaries.return_value = load_json_object_fixture(
            "GetPlayerSummaries.json", DOMAIN
        )

        yield mock_client
