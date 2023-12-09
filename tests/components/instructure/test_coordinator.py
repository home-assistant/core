"""Test the coordinator."""
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.instructure.const import (
    ANNOUNCEMENTS_KEY,
    ASSIGNMENTS_KEY,
    CONVERSATIONS_KEY,
    GRADES_KEY,
)
from homeassistant.components.instructure.coordinator import CanvasUpdateCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import MOCK_ANNOUNCEMENTS, MOCK_ASSIGNMENTS, MOCK_CONVERSATIONS, MOCK_GRADES


@pytest.fixture
def mock_api():
    """Return a mock CanvasAPI object."""
    with patch("homeassistant.components.instructure.CanvasAPI", autospec=True) as mock:
        mock_instance = mock.return_value
        mock_instance.async_get_upcoming_assignments = AsyncMock(
            return_value=MOCK_ASSIGNMENTS
        )
        mock_instance.async_get_announcements = AsyncMock(
            return_value=MOCK_ANNOUNCEMENTS
        )
        mock_instance.async_get_conversations = AsyncMock(
            return_value=MOCK_CONVERSATIONS
        )
        mock_instance.async_get_grades = AsyncMock(return_value=MOCK_GRADES)
        yield mock_instance


@pytest.fixture
def mock_coordinator(hass: HomeAssistant, mock_api, mock_config_entry):
    """Return a mock CanvasUpdateCoordinator object."""
    coordinator = CanvasUpdateCoordinator(hass, mock_config_entry, mock_api)
    return coordinator


async def test_async_update_data_success(hass: HomeAssistant, mock_coordinator) -> None:
    """Test the async_update_data method success."""
    data = await mock_coordinator.async_update_data()
    assert data[ASSIGNMENTS_KEY] == MOCK_ASSIGNMENTS
    assert data[ANNOUNCEMENTS_KEY] == MOCK_ANNOUNCEMENTS
    assert data[CONVERSATIONS_KEY] == MOCK_CONVERSATIONS
    assert data[GRADES_KEY] == MOCK_GRADES


async def test_async_update_data_failure(
    hass: HomeAssistant, mock_coordinator, mock_api
) -> None:
    """Test the async_update_data method failure."""
    mock_api.async_get_upcoming_assignments.side_effect = HomeAssistantError
    with pytest.raises(UpdateFailed) as exc_info:
        await mock_coordinator.async_update_data()

    assert "Error communicating with API" in str(exc_info.value)


async def test_get_quick_links_file_not_found(
    hass: HomeAssistant, mock_coordinator
) -> None:
    """Test the get_quick_links method when file is not found."""
    with patch("builtins.open", side_effect=FileNotFoundError):
        links = mock_coordinator.get_quick_links()
        assert links == {}


async def test_update_with_empty_assignments(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test empty assignment api call for coordinator."""
    with patch("homeassistant.components.instructure.CanvasAPI", autospec=True) as mock:
        mock_instance = mock.return_value
        mock_instance.async_get_upcoming_assignments = AsyncMock(return_value={})
        mock_instance.async_get_announcements = AsyncMock(
            return_value=MOCK_ANNOUNCEMENTS
        )
        mock_instance.async_get_conversations = AsyncMock(
            return_value=MOCK_CONVERSATIONS
        )
        mock_instance.async_get_grades = AsyncMock(return_value=MOCK_GRADES)

        coordinator = CanvasUpdateCoordinator(hass, mock_config_entry, mock_instance)

        data = await coordinator.async_update_data()
        assert data[ASSIGNMENTS_KEY] == {}
        assert data[ANNOUNCEMENTS_KEY] == MOCK_ANNOUNCEMENTS
        assert data[CONVERSATIONS_KEY] == MOCK_CONVERSATIONS
        assert data[GRADES_KEY] == MOCK_GRADES


async def test_update_with_all_empty_data(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test Empty api calls."""
    with patch("homeassistant.components.instructure.CanvasAPI", autospec=True) as mock:
        mock_instance = mock.return_value
        mock_instance.async_get_upcoming_assignments = AsyncMock(return_value={})
        mock_instance.async_get_announcements = AsyncMock(return_value={})
        mock_instance.async_get_conversations = AsyncMock(return_value={})
        mock_instance.async_get_grades = AsyncMock(return_value={})

        coordinator = CanvasUpdateCoordinator(hass, mock_config_entry, mock_instance)

        data = await coordinator.async_update_data()
        assert data[ASSIGNMENTS_KEY] == {}
        assert data[ANNOUNCEMENTS_KEY] == {}
        assert data[CONVERSATIONS_KEY] == {}
        assert data[GRADES_KEY] == {}
