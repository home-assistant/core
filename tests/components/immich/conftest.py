"""Common fixtures for the Immich tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

from aioimmich.server.models import (
    ImmichServerAbout,
    ImmichServerStatistics,
    ImmichServerStorage,
)
import pytest


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.immich.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_immich_data():
    """Mock the immich data."""
    return {
        "server_about": ImmichServerAbout(
            "v1.132.3",
            "some_url",
            False,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
        ),
        "server_storage": ImmichServerStorage(
            "294.2 GiB",
            "142.9 GiB",
            "136.3 GiB",
            315926315008,
            153400434688,
            146402975744,
            48.56,
        ),
        "server_usage": ImmichServerStatistics(
            27038, 1836, 119525451912, 54291170551, 65234281361
        ),
    }


@pytest.fixture
def mock_immich(mock_immich_data) -> Mock:
    """Mock the Immich API."""
    return Mock(
        server=Mock(
            async_get_about_info=AsyncMock(
                return_value=mock_immich_data["server_about"]
            ),
            async_get_storage_info=AsyncMock(
                return_value=mock_immich_data["server_storage"]
            ),
            async_get_server_statistics=AsyncMock(
                return_value=mock_immich_data["server_usage"]
            ),
        )
    )
