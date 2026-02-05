"""Fixtures for Ghost integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from aioghost.exceptions import GhostAuthError, GhostConnectionError
import pytest

from homeassistant.components.ghost.const import (
    CONF_ADMIN_API_KEY,
    CONF_API_URL,
    DOMAIN,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

API_URL = "https://test.ghost.io"
API_KEY = "650b7a9f8e8c1234567890ab:1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
SITE_UUID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Test Ghost",
        data={
            CONF_API_URL: API_URL,
            CONF_ADMIN_API_KEY: API_KEY,
        },
        unique_id=SITE_UUID,
    )


@pytest.fixture
def mock_ghost_data() -> dict:
    """Return mock Ghost API data."""
    return {
        "site": {"title": "Test Ghost", "url": API_URL, "uuid": SITE_UUID},
        "posts": {"published": 42, "drafts": 5, "scheduled": 2},
        "members": {"total": 1000, "paid": 100, "free": 850, "comped": 50},
        "latest_post": {
            "title": "Latest Post",
            "slug": "latest-post",
            "url": f"{API_URL}/latest-post/",
            "published_at": "2026-01-15T10:00:00Z",
        },
        "latest_email": {
            "title": "Newsletter #1",
            "subject": "Newsletter #1",
            "email_count": 500,
            "delivered_count": 490,
            "opened_count": 200,
            "clicked_count": 50,
            "failed_count": 10,
            "open_rate": 40,
            "click_rate": 10,
            "submitted_at": "2026-01-15T10:00:00Z",
        },
        "activitypub": {"followers": 150, "following": 25},
        "mrr": {"usd": 5000},
        "arr": {"usd": 60000},
        "comments": 156,
        "newsletters": [
            {
                "id": "nl1",
                "name": "Weekly",
                "status": "active",
                "count": {"members": 800},
            },
            {
                "id": "nl2",
                "name": "Archive",
                "status": "archived",
                "count": {"members": 200},
            },
        ],
    }


@pytest.fixture
def mock_ghost_api(mock_ghost_data: dict) -> Generator[AsyncMock]:
    """Mock the GhostAdminAPI."""
    with patch("homeassistant.components.ghost.GhostAdminAPI") as mock_api_class:
        mock_api = AsyncMock()
        mock_api.api_url = API_URL
        mock_api.get_site.return_value = mock_ghost_data["site"]
        mock_api.get_posts_count.return_value = mock_ghost_data["posts"]
        mock_api.get_members_count.return_value = mock_ghost_data["members"]
        mock_api.get_latest_post.return_value = mock_ghost_data["latest_post"]
        mock_api.get_latest_email.return_value = mock_ghost_data["latest_email"]
        mock_api.get_activitypub_stats.return_value = mock_ghost_data["activitypub"]
        mock_api.get_mrr.return_value = mock_ghost_data["mrr"]
        mock_api.get_arr.return_value = mock_ghost_data["arr"]
        mock_api.get_comments_count.return_value = mock_ghost_data["comments"]
        mock_api.get_newsletters.return_value = mock_ghost_data["newsletters"]
        mock_api.close.return_value = None
        mock_api_class.return_value = mock_api
        yield mock_api


@pytest.fixture
def mock_ghost_api_auth_error() -> Generator[AsyncMock]:
    """Mock GhostAdminAPI that raises auth error."""
    with patch("homeassistant.components.ghost.GhostAdminAPI") as mock_api_class:
        mock_api = AsyncMock()
        mock_api.get_site.side_effect = GhostAuthError("Invalid API key")
        mock_api.close.return_value = None
        mock_api_class.return_value = mock_api
        yield mock_api


@pytest.fixture
def mock_ghost_api_connection_error() -> Generator[AsyncMock]:
    """Mock GhostAdminAPI that raises connection error."""
    with patch("homeassistant.components.ghost.GhostAdminAPI") as mock_api_class:
        mock_api = AsyncMock()
        mock_api.get_site.side_effect = GhostConnectionError("Connection failed")
        mock_api.close.return_value = None
        mock_api_class.return_value = mock_api
        yield mock_api
