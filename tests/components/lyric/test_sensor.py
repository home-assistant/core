"""Tests for the Honeywell Lyric sensor platform."""

from datetime import datetime
from unittest.mock import patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.lyric.sensor import get_datetime_from_future_time
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import async_setup_lyric_entry

from tests.common import MockConfigEntry, snapshot_platform


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


async def test_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_credentials: None,
    mock_lyric_api: None,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Lyric sensor platform via a real config entry setup."""
    with patch("homeassistant.components.lyric.PLATFORMS", [Platform.SENSOR]):
        await async_setup_lyric_entry(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
