"""Test persistence logic for Diyanet integration."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.diyanet.coordinator import DiyanetCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

pytest_plugins = ["pytest_asyncio"]


@pytest.fixture
async def mock_coordinator(hass: HomeAssistant):
    """Return a coordinator with mocked API client and config entry."""
    api_client = MagicMock()
    api_client.get_prayer_times = AsyncMock(
        return_value={
            "gregorianDateLong": datetime.now().strftime("%d %B %Y"),
            "fajr": "06:00",
        }
    )
    config_entry = MagicMock()
    config_entry.entry_id = "test_entry"
    return DiyanetCoordinator(hass, api_client, 12345, config_entry)


@pytest.mark.asyncio
async def test_cache_used_for_today(mock_coordinator) -> None:
    """Test that cached data for today is used and no API call is made."""
    today_str = datetime.now().strftime("%d %B %Y")
    cached_data = {"gregorianDateLong": today_str, "fajr": "06:00"}
    with (
        patch.object(Store, "async_load", return_value=cached_data),
        patch.object(
            mock_coordinator.client, "get_prayer_times", new_callable=AsyncMock
        ) as mock_api,
    ):
        data = await mock_coordinator._async_update_data()
        assert data["gregorianDateLong"] == today_str
        assert not mock_api.called


@pytest.mark.asyncio
async def test_cache_outdated_triggers_fetch(mock_coordinator) -> None:
    """Test that outdated cached data triggers API fetch and cache update."""
    yesterday = datetime.now() - timedelta(days=1)
    yesterday_str = yesterday.strftime("%d %B %Y")
    cached_data = {"gregorianDateLong": yesterday_str, "fajr": "05:59"}
    with (
        patch.object(Store, "async_load", return_value=cached_data),
        patch.object(
            mock_coordinator.client, "get_prayer_times", new_callable=AsyncMock
        ) as mock_api,
        patch.object(Store, "async_save", new_callable=AsyncMock) as mock_save,
    ):
        mock_api.return_value = {
            "gregorianDateLong": datetime.now().strftime("%d %B %Y"),
            "fajr": "06:00",
        }
        data = await mock_coordinator._async_update_data()
        assert data["gregorianDateLong"] != yesterday_str
        assert mock_api.called
        assert mock_save.called
