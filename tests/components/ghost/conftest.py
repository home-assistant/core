"""Fixtures for Ghost integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.ghost.const import (
    CONF_ADMIN_API_KEY,
    CONF_API_URL,
    DOMAIN,
)

from tests.common import MockConfigEntry

API_URL = "https://test.ghost.io"
API_KEY = "650b7a9f8e8c1234567890ab:1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
SITE_UUID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
SITE_DATA = {"title": "Test Ghost", "url": API_URL, "uuid": SITE_UUID}
POSTS_DATA = {"published": 42, "drafts": 5, "scheduled": 2}
MEMBERS_DATA = {"total": 1000, "paid": 100, "free": 850, "comped": 50}
LATEST_POST_DATA = {
    "title": "Latest Post",
    "slug": "latest-post",
    "url": f"{API_URL}/latest-post/",
    "published_at": "2026-01-15T10:00:00Z",
}
LATEST_EMAIL_DATA = {
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
}
ACTIVITYPUB_DATA = {"followers": 150, "following": 25}
MRR_DATA = {"usd": 5000}
ARR_DATA = {"usd": 60000}
COMMENTS_COUNT = 156
NEWSLETTERS_DATA = [
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
]


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
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
def mock_ghost_api() -> Generator[AsyncMock]:
    """Mock the GhostAdminAPI."""
    with (
        patch(
            "homeassistant.components.ghost.GhostAdminAPI", autospec=True
        ) as mock_api_class,
        patch(
            "homeassistant.components.ghost.config_flow.GhostAdminAPI",
            new=mock_api_class,
        ),
    ):
        mock_api = mock_api_class.return_value
        mock_api.api_url = API_URL
        mock_api.get_site.return_value = SITE_DATA
        mock_api.get_posts_count.return_value = POSTS_DATA
        mock_api.get_members_count.return_value = MEMBERS_DATA
        mock_api.get_latest_post.return_value = LATEST_POST_DATA
        mock_api.get_latest_email.return_value = LATEST_EMAIL_DATA
        mock_api.get_activitypub_stats.return_value = ACTIVITYPUB_DATA
        mock_api.get_mrr.return_value = MRR_DATA
        mock_api.get_arr.return_value = ARR_DATA
        mock_api.get_comments_count.return_value = COMMENTS_COUNT
        mock_api.get_newsletters.return_value = NEWSLETTERS_DATA
        mock_api.close.return_value = None
        yield mock_api


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setup entry."""
    with patch(
        "homeassistant.components.ghost.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup
