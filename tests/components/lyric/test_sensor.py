"""Tests for the Honeywell Lyric sensor platform."""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from homeassistant.components.lyric.sensor import (
    LyricPriorityStatusSensor,
    get_datetime_from_future_time,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MAC_ID, async_setup_lyric_entry

from tests.common import MockConfigEntry


def test_get_datetime_from_future_time_none() -> None:
    """Test that None input returns None instead of raising."""
    assert get_datetime_from_future_time(None) is None


def test_get_datetime_from_future_time_invalid() -> None:
    """Test that an unparsable time string returns None."""
    assert get_datetime_from_future_time("not_a_time") is None


def test_get_datetime_from_future_time_valid() -> None:
    """Test that a valid time string returns a datetime."""
    result = get_datetime_from_future_time("13:30:00")
    assert isinstance(result, datetime)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "aiolyric 2.1.1's LyricPriority.current_priority reads JSON key "
        "'currentPriority' instead of the live API's 'priority', so "
        "rooms_dict never populates and this entity's creation gate never "
        "passes. Fixed upstream in timmo001/aiolyric#165 (which also fixes "
        "LyricPriority.status reading 'status' instead of the live API's "
        "'priorityStatus'); once that's released and the manifest pin is "
        "bumped, this will start passing for real and this marker must be "
        "removed."
    ),
)
async def test_priority_status_created(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_credentials: None,
    mock_lyric_api: None,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Priority Status should be created via a real config entry setup."""
    await async_setup_lyric_entry(hass, mock_config_entry)

    entity_id = entity_registry.async_get_entity_id(
        "sensor", "lyric", f"{MAC_ID}_priority_status"
    )
    assert entity_id
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "NoHold"


def test_priority_status_native_value_returns_status() -> None:
    """Priority Status reads priority.status when data is present."""
    coordinator = MagicMock()
    coordinator.data.priorities_dict = {MAC_ID: MagicMock(status="NoHold")}
    device = MagicMock(mac_id=MAC_ID)

    sensor = LyricPriorityStatusSensor(coordinator, MagicMock(), device)

    assert sensor.native_value == "NoHold"


def test_priority_status_native_value_returns_none_when_missing() -> None:
    """Priority Status is None when no priority data exists for the device."""
    coordinator = MagicMock()
    coordinator.data.priorities_dict = {}
    device = MagicMock(mac_id=MAC_ID)

    sensor = LyricPriorityStatusSensor(coordinator, MagicMock(), device)

    assert sensor.native_value is None
