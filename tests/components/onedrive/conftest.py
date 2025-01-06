"""Fixtures for OneDrive tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from msgraph.generated.models.drive import Drive
import pytest


@pytest.fixture
def mock_drive() -> Generator[Drive]:
    """Return a mocked Drive."""
    drive = Drive()
    drive.id = "mock_drive_id"
    return drive


@pytest.fixture
def mock_graph_client(mock_drive: Drive) -> Generator[MagicMock]:
    """Return a mocked GraphServiceClient."""
    with (
        patch(
            "homeassistant.components.onedrive.config_flow.GraphServiceClient",
            autospec=True,
        ) as graph_client,
        patch(
            "homeassistant.components.onedrive.GraphServiceClient",
            new=graph_client,
        ),
    ):
        client = graph_client.return_value
        client.me.drive.get = AsyncMock()
        client.me.drive.get.return_value = mock_drive
        yield client


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.onedrive.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
