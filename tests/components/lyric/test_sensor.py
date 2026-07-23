"""Tests for the Honeywell Lyric sensor platform."""

from datetime import datetime

from homeassistant.components.lyric.sensor import get_datetime_from_future_time
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MAC_ID, async_setup_lyric_entry

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


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


async def test_schedule_status_sensor_end_to_end(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_credentials: None,
    mock_lyric_api: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the schedule status diagnostic sensor via a real config entry setup.

    scheduleStatus comes from the base /locations response (not the
    /priority endpoint), so it has no known aiolyric field-name mismatch
    and passes for real against the currently-pinned release.
    """
    await async_setup_lyric_entry(hass, mock_config_entry)

    entity_id = entity_registry.async_get_entity_id(
        "sensor", "lyric", f"{MAC_ID}_schedule_status"
    )
    assert entity_id
    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.entity_category is EntityCategory.DIAGNOSTIC

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "Resume"
