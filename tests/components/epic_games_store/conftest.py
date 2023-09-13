"""Define fixtures for Epic Games Store tests."""
from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from .const import DATA_FREE_GAMES


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.epic_games_store.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="service_multiple")
def mock_service_multiple():
    """Mock a successful service with multiple free & discount games."""
    with patch(
        "homeassistant.components.epic_games_store.coordinator.EpicGamesStoreAPI"
    ) as service_mock:
        instance = service_mock.return_value
        instance.get_free_games = AsyncMock(return_value=DATA_FREE_GAMES)
        yield service_mock
