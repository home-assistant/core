"""Tests for Ghost data coordinator."""

from datetime import timedelta
from unittest.mock import AsyncMock

from aioghost.exceptions import GhostAuthError, GhostConnectionError, GhostError
import pytest

from homeassistant.components.ghost.const import (
    CONF_ADMIN_API_KEY,
    CONF_API_URL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from homeassistant.components.ghost.coordinator import GhostDataUpdateCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from .conftest import API_KEY, API_URL

from tests.common import MockConfigEntry


async def test_coordinator_update(
    hass: HomeAssistant, mock_ghost_api: AsyncMock, mock_ghost_data: dict
) -> None:
    """Test coordinator fetches data successfully."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Ghost",
        data={CONF_API_URL: API_URL, CONF_ADMIN_API_KEY: API_KEY},
    )
    entry.add_to_hass(hass)
    coordinator = GhostDataUpdateCoordinator(hass, mock_ghost_api, entry)

    await coordinator.async_refresh()

    assert coordinator.data is not None
    assert coordinator.data.site["title"] == "Test Ghost"
    assert coordinator.data.members["total"] == 1000
    assert coordinator.data.posts["published"] == 42


async def test_coordinator_parallel_requests(
    hass: HomeAssistant, mock_ghost_api: AsyncMock
) -> None:
    """Test coordinator makes parallel API requests."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Ghost",
        data={CONF_API_URL: API_URL, CONF_ADMIN_API_KEY: API_KEY},
    )
    entry.add_to_hass(hass)
    coordinator = GhostDataUpdateCoordinator(hass, mock_ghost_api, entry)

    await coordinator.async_refresh()

    # Verify all API methods were called
    mock_ghost_api.get_site.assert_called_once()
    mock_ghost_api.get_posts_count.assert_called_once()
    mock_ghost_api.get_members_count.assert_called_once()
    mock_ghost_api.get_latest_post.assert_called_once()
    mock_ghost_api.get_latest_email.assert_called_once()
    mock_ghost_api.get_activitypub_stats.assert_called_once()
    mock_ghost_api.get_mrr.assert_called_once()
    mock_ghost_api.get_arr.assert_called_once()
    mock_ghost_api.get_comments_count.assert_called_once()
    mock_ghost_api.get_newsletters.assert_called_once()


async def test_coordinator_auth_error(hass: HomeAssistant) -> None:
    """Test coordinator raises ConfigEntryAuthFailed on auth error."""
    mock_api = AsyncMock()
    # Set all methods to raise auth error since gather calls them all
    mock_api.get_site.side_effect = GhostAuthError("Invalid API key")
    mock_api.get_posts_count.side_effect = GhostAuthError("Invalid API key")
    mock_api.get_members_count.side_effect = GhostAuthError("Invalid API key")
    mock_api.get_latest_post.side_effect = GhostAuthError("Invalid API key")
    mock_api.get_latest_email.side_effect = GhostAuthError("Invalid API key")
    mock_api.get_activitypub_stats.side_effect = GhostAuthError("Invalid API key")
    mock_api.get_mrr.side_effect = GhostAuthError("Invalid API key")
    mock_api.get_arr.side_effect = GhostAuthError("Invalid API key")
    mock_api.get_comments_count.side_effect = GhostAuthError("Invalid API key")
    mock_api.get_newsletters.side_effect = GhostAuthError("Invalid API key")

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Ghost",
        data={CONF_API_URL: API_URL, CONF_ADMIN_API_KEY: API_KEY},
    )
    entry.add_to_hass(hass)
    coordinator = GhostDataUpdateCoordinator(hass, mock_api, entry)

    with pytest.raises(ConfigEntryAuthFailed) as exc_info:
        await coordinator._async_update_data()
    assert exc_info.value.translation_key == "invalid_api_key"


async def test_coordinator_connection_error(hass: HomeAssistant) -> None:
    """Test coordinator raises UpdateFailed on connection error."""
    mock_api = AsyncMock()
    mock_api.get_site.side_effect = GhostConnectionError("Connection failed")
    mock_api.get_posts_count.side_effect = GhostConnectionError("Connection failed")
    mock_api.get_members_count.side_effect = GhostConnectionError("Connection failed")
    mock_api.get_latest_post.side_effect = GhostConnectionError("Connection failed")
    mock_api.get_latest_email.side_effect = GhostConnectionError("Connection failed")
    mock_api.get_activitypub_stats.side_effect = GhostConnectionError(
        "Connection failed"
    )
    mock_api.get_mrr.side_effect = GhostConnectionError("Connection failed")
    mock_api.get_arr.side_effect = GhostConnectionError("Connection failed")
    mock_api.get_comments_count.side_effect = GhostConnectionError("Connection failed")
    mock_api.get_newsletters.side_effect = GhostConnectionError("Connection failed")

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Ghost",
        data={CONF_API_URL: API_URL, CONF_ADMIN_API_KEY: API_KEY},
    )
    entry.add_to_hass(hass)
    coordinator = GhostDataUpdateCoordinator(hass, mock_api, entry)

    with pytest.raises(UpdateFailed) as exc_info:
        await coordinator._async_update_data()
    assert exc_info.value.translation_key == "api_error"


async def test_coordinator_generic_error(hass: HomeAssistant) -> None:
    """Test coordinator raises UpdateFailed on generic error."""
    mock_api = AsyncMock()
    mock_api.get_site.side_effect = GhostError("Something went wrong")
    mock_api.get_posts_count.side_effect = GhostError("Something went wrong")
    mock_api.get_members_count.side_effect = GhostError("Something went wrong")
    mock_api.get_latest_post.side_effect = GhostError("Something went wrong")
    mock_api.get_latest_email.side_effect = GhostError("Something went wrong")
    mock_api.get_activitypub_stats.side_effect = GhostError("Something went wrong")
    mock_api.get_mrr.side_effect = GhostError("Something went wrong")
    mock_api.get_arr.side_effect = GhostError("Something went wrong")
    mock_api.get_comments_count.side_effect = GhostError("Something went wrong")
    mock_api.get_newsletters.side_effect = GhostError("Something went wrong")

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Ghost",
        data={CONF_API_URL: API_URL, CONF_ADMIN_API_KEY: API_KEY},
    )
    entry.add_to_hass(hass)
    coordinator = GhostDataUpdateCoordinator(hass, mock_api, entry)

    with pytest.raises(UpdateFailed) as exc_info:
        await coordinator._async_update_data()
    assert exc_info.value.translation_key == "api_error"


async def test_coordinator_name(hass: HomeAssistant, mock_ghost_api: AsyncMock) -> None:
    """Test coordinator has correct name."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="My Site",
        data={CONF_API_URL: API_URL, CONF_ADMIN_API_KEY: API_KEY},
    )
    entry.add_to_hass(hass)
    coordinator = GhostDataUpdateCoordinator(hass, mock_ghost_api, entry)

    assert coordinator.name == "Ghost (My Site)"


async def test_coordinator_update_interval(
    hass: HomeAssistant, mock_ghost_api: AsyncMock
) -> None:
    """Test coordinator has correct update interval."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Ghost",
        data={CONF_API_URL: API_URL, CONF_ADMIN_API_KEY: API_KEY},
    )
    entry.add_to_hass(hass)
    coordinator = GhostDataUpdateCoordinator(hass, mock_ghost_api, entry)

    assert coordinator.update_interval == timedelta(seconds=DEFAULT_SCAN_INTERVAL)
