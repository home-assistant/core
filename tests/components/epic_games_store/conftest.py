"""Define fixtures for Epic Games Store tests."""
from unittest.mock import Mock, patch

import pytest

from .const import DATA_FREE_GAMES


@pytest.fixture(name="service_multiple")
def mock_service_multiple():
    """Mock a successful service with multiple free & discount games."""
    with patch(
        "homeassistant.components.epic_games_store.coordinator.EpicGamesStoreAPI"
    ) as service_mock:
        instance = service_mock.return_value
        instance.get_free_games = Mock(return_value=DATA_FREE_GAMES)
        yield service_mock
