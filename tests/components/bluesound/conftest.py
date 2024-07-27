"""Common fixtures for the Bluesound tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from aiohttp import ClientConnectionError
from pyblu import SyncStatus
import pytest


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.bluesound.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_player_sync_status() -> Generator[AsyncMock, None, None]:
    """Mock the sync status of a player."""
    with patch(
        "pyblu.Player.sync_status",
        new_callable=AsyncMock,
    ) as mock_sync_status:
        mock_sync_status.return_value = SyncStatus(
            etag="etag",
            id="1.1.1.1:11000",
            mac="00:11:22:33:44:55",
            name="player-name",
            image="invalid_url",
            initialized=True,
            brand="brand",
            model="model",
            model_name="model-name",
            volume_db=0.5,
            volume=50,
            group=None,
            master=None,
            slaves=None,
            zone=None,
            zone_master=None,
            zone_slave=None,
            mute_volume_db=None,
            mute_volume=None,
        )
        yield mock_sync_status


@pytest.fixture
def mock_player_sync_status_client_connection_error() -> (
    Generator[AsyncMock, None, None]
):
    """Mock the sync status of a player with a group."""
    with patch(
        "pyblu.Player.sync_status",
        side_effect=ClientConnectionError,
    ) as mock_sync_status:
        yield mock_sync_status
