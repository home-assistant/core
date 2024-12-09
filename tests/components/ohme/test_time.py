"""Tests for time entity."""

from datetime import time as dt_time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.ohme.time import TargetTime, async_setup_entry


@pytest.fixture
def mock_config_entry():
    """Fixture for creating a mock config entry."""
    return AsyncMock(data={"email": "test@example.com"})


@pytest.mark.asyncio
async def test_async_setup_entry(mock_config_entry) -> None:
    """Test async_setup_entry."""
    mock_async_add_entities = AsyncMock()
    await async_setup_entry(MagicMock(), mock_config_entry, mock_async_add_entities)
    assert mock_async_add_entities.called


@pytest.fixture
def target_time_entity() -> None:
    """Fixture for creating a target time entity."""
    entity = TargetTime(AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock())
    entity.platform = AsyncMock()
    return entity


@pytest.mark.asyncio
async def test_async_added_to_hass(target_time_entity) -> None:
    """Test async_added_to_hass."""
    with patch.object(
        target_time_entity.coordinator_schedules,
        "async_add_listener",
        return_value=AsyncMock(),
    ) as mock_add_listener:
        await target_time_entity.async_added_to_hass()
        assert mock_add_listener.called


@pytest.mark.asyncio
async def test_async_set_value(target_time_entity) -> None:
    """Test async_set_value."""
    with patch(
        "homeassistant.components.ohme.time.session_in_progress", return_value=True
    ):
        await target_time_entity.async_set_value(dt_time(12, 30))
        assert target_time_entity._client.async_apply_session_rule.called

    with patch(
        "homeassistant.components.ohme.time.session_in_progress", return_value=False
    ):
        await target_time_entity.async_set_value(dt_time(12, 30))
        assert target_time_entity._client.async_update_schedule.called


def test_native_value(target_time_entity) -> None:
    """Test native_value."""
    target_time_entity._state = dt_time(12, 30)
    assert target_time_entity.native_value == dt_time(12, 30)
