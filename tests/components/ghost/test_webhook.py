"""Tests for Ghost webhook handling."""

from unittest.mock import AsyncMock, MagicMock

from aiohttp import web

from homeassistant.components.ghost.webhook import handle_webhook
from homeassistant.core import HomeAssistant

from tests.common import async_capture_events


def _create_mock_request(payload: dict) -> MagicMock:
    """Create a mock aiohttp request with JSON payload."""
    request = MagicMock(spec=web.Request)
    request.json = AsyncMock(return_value=payload)
    return request


async def test_webhook_member_added(hass: HomeAssistant) -> None:
    """Test handling member.added webhook."""
    events = async_capture_events(hass, "ghost_member_added")

    request = _create_mock_request(
        {
            "member": {
                "current": {
                    "id": "member123",
                    "email": "test@example.com",
                    "name": "Test User",
                    "status": "free",
                },
                "previous": {},
            }
        }
    )

    response = await handle_webhook(hass, "ghost_test", request)
    await hass.async_block_till_done()

    assert response.status == 200
    assert len(events) == 1
    assert events[0].data["member_id"] == "member123"
    assert events[0].data["email"] == "test@example.com"


async def test_webhook_member_deleted(hass: HomeAssistant) -> None:
    """Test handling member.deleted webhook."""
    events = async_capture_events(hass, "ghost_member_deleted")

    request = _create_mock_request(
        {
            "member": {
                "current": {},
                "previous": {
                    "id": "member123",
                    "email": "deleted@example.com",
                    "name": "Deleted User",
                    "status": "paid",
                },
            }
        }
    )

    response = await handle_webhook(hass, "ghost_test", request)
    await hass.async_block_till_done()

    assert response.status == 200
    assert len(events) == 1
    assert events[0].data["member_id"] == "member123"


async def test_webhook_member_edited_ignored(hass: HomeAssistant) -> None:
    """Test that member.edited webhook is ignored (too high volume)."""
    events_added = async_capture_events(hass, "ghost_member_added")
    events_deleted = async_capture_events(hass, "ghost_member_deleted")

    request = _create_mock_request(
        {
            "member": {
                "current": {
                    "id": "member123",
                    "email": "test@example.com",
                    "name": "Updated Name",
                    "status": "free",
                },
                "previous": {
                    "name": "Old Name",
                },
            }
        }
    )

    response = await handle_webhook(hass, "ghost_test", request)
    await hass.async_block_till_done()

    assert response.status == 200
    # No event should be fired for member.edited
    assert len(events_added) == 0
    assert len(events_deleted) == 0


async def test_webhook_post_published(hass: HomeAssistant) -> None:
    """Test handling post.published webhook."""
    events = async_capture_events(hass, "ghost_post_published")

    request = _create_mock_request(
        {
            "post": {
                "current": {
                    "id": "post123",
                    "title": "New Post",
                    "slug": "new-post",
                    "status": "published",
                    "url": "https://example.com/new-post/",
                },
                "previous": {
                    "status": "draft",
                },
            }
        }
    )

    response = await handle_webhook(hass, "ghost_test", request)
    await hass.async_block_till_done()

    assert response.status == 200
    assert len(events) == 1
    assert events[0].data["title"] == "New Post"


async def test_webhook_post_unpublished(hass: HomeAssistant) -> None:
    """Test handling post unpublished webhook."""
    events = async_capture_events(hass, "ghost_post_unpublished")

    request = _create_mock_request(
        {
            "post": {
                "current": {
                    "id": "post123",
                    "title": "Old Post",
                    "slug": "old-post",
                    "status": "draft",
                },
                "previous": {
                    "status": "published",
                },
            }
        }
    )

    response = await handle_webhook(hass, "ghost_test", request)
    await hass.async_block_till_done()

    assert response.status == 200
    assert len(events) == 1


async def test_webhook_post_updated(hass: HomeAssistant) -> None:
    """Test handling post.updated webhook (status unchanged)."""
    events = async_capture_events(hass, "ghost_post_updated")

    # When status doesn't change, Ghost sends previous status in the payload
    request = _create_mock_request(
        {
            "post": {
                "current": {
                    "id": "post123",
                    "title": "Updated Post",
                    "slug": "post",
                    "status": "published",
                },
                "previous": {
                    "title": "Old Title",
                    "status": "published",  # Same status = update, not publish
                },
            }
        }
    )

    response = await handle_webhook(hass, "ghost_test", request)
    await hass.async_block_till_done()

    assert response.status == 200
    assert len(events) == 1


async def test_webhook_page_published(hass: HomeAssistant) -> None:
    """Test handling page.published webhook."""
    events = async_capture_events(hass, "ghost_page_published")

    request = _create_mock_request(
        {
            "page": {
                "current": {
                    "id": "page123",
                    "title": "About Page",
                    "slug": "about",
                    "status": "published",
                    "url": "https://example.com/about/",
                },
                "previous": {
                    "status": "draft",
                },
            }
        }
    )

    response = await handle_webhook(hass, "ghost_test", request)
    await hass.async_block_till_done()

    assert response.status == 200
    assert len(events) == 1


async def test_webhook_invalid_json(hass: HomeAssistant) -> None:
    """Test handling invalid JSON payload."""
    request = MagicMock(spec=web.Request)
    request.json = AsyncMock(side_effect=ValueError("Invalid JSON"))

    response = await handle_webhook(hass, "ghost_test", request)

    assert response.status == 400


async def test_webhook_unknown_payload(hass: HomeAssistant) -> None:
    """Test handling unknown webhook payload."""
    events = async_capture_events(hass, "ghost_member_added")

    request = _create_mock_request({"unknown": {"data": "test"}})

    response = await handle_webhook(hass, "ghost_test", request)
    await hass.async_block_till_done()

    assert response.status == 200
    # No event should be fired for unknown payload
    assert len(events) == 0
