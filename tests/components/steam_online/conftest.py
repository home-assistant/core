"""Common fixtures for the Steam integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.steam_online.const import DOMAIN, SUBENTRY_TYPE_FRIEND
from homeassistant.config_entries import ConfigSubentryData

from . import ACCOUNT_1, ACCOUNT_2, ACCOUNT_NAME_2, CONF_DATA

from tests.common import MockConfigEntry, load_json_object_fixture, patch


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Mock Steam configuration entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=CONF_DATA,
        unique_id=ACCOUNT_1,
        subentries_data=[
            ConfigSubentryData(
                data={},
                subentry_type=SUBENTRY_TYPE_FRIEND,
                title=ACCOUNT_NAME_2,
                unique_id=ACCOUNT_2,
            ),
        ],
        version=3,
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
            "homeassistant.components.steam_online.coordinator.steam.api.interface",
            new=mock_client,
        ),
        patch("homeassistant.components.steam_online.coordinator.steam.api.key.set"),
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
