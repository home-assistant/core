"""Define fixtures for Epic Games Store tests."""

from unittest.mock import Mock, patch

import pytest

from .const import (
    DATA_ERROR_ATTRIBUTE_NOT_FOUND,
    DATA_FREE_GAMES,
    DATA_FREE_GAMES_CHRISTMAS_SPECIAL,
)


@pytest.fixture(name="service_multiple")
def mock_service_multiple():
    """Mock a successful service with multiple free & discount games."""
    with patch(
        "homeassistant.components.epic_games_store.coordinator.EpicGamesStoreAPI"
    ) as service_mock:
        instance = service_mock.return_value
        instance.get_free_games = Mock(return_value=DATA_FREE_GAMES)
        yield service_mock


@pytest.fixture(name="service_christmas_special")
def mock_service_christmas_special():
    """Mock a successful service with Christmas special case."""
    with patch(
        "homeassistant.components.epic_games_store.coordinator.EpicGamesStoreAPI"
    ) as service_mock:
        instance = service_mock.return_value
        instance.get_free_games = Mock(return_value=DATA_FREE_GAMES_CHRISTMAS_SPECIAL)
        yield service_mock


@pytest.fixture(name="service_attribute_not_found")
def mock_service_attribute_not_found():
    """Mock a successful service returning a not found attribute error with free & discount games."""
    with patch(
        "homeassistant.components.epic_games_store.coordinator.EpicGamesStoreAPI"
    ) as service_mock:
        instance = service_mock.return_value
        instance.get_free_games = Mock(return_value=DATA_ERROR_ATTRIBUTE_NOT_FOUND)
        yield service_mock
