"""Tests for the Honeywell Lyric sensor platform."""

from datetime import datetime
from unittest.mock import MagicMock

from aiolyric.objects.device import LyricDevice

from homeassistant.components.lyric.sensor import (
    async_setup_entry,
    get_datetime_from_future_time,
)
from homeassistant.const import EntityCategory


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


async def test_schedule_status_sensor_end_to_end() -> None:
    """Schedule Status is created as a diagnostic sensor with the real value.

    Built from a real LyricDevice parsed from a live-shaped payload (not a
    pre-set mock), exercising the actual aiolyric parsing boundary through
    to the entity's native_value. scheduleStatus has no known aiolyric
    field-name mismatch, so this is expected to pass today.
    """
    mac_id = "5CFCE1B67035"
    device = LyricDevice(
        MagicMock(),
        {
            "macID": mac_id,
            "units": "Fahrenheit",
            "scheduleStatus": "Resume",
        },
    )
    location = MagicMock()
    location.location_id = "location1"
    location.devices = [device]
    location.devices_dict = {mac_id: device}

    coordinator = MagicMock()
    coordinator.data.locations = [location]
    coordinator.data.locations_dict = {"location1": location}
    coordinator.data.rooms_dict = {}

    entry = MagicMock()
    entry.runtime_data = coordinator

    added: list[list] = []
    async_add_entities = MagicMock(
        side_effect=lambda entities: added.append(list(entities))
    )

    await async_setup_entry(MagicMock(), entry, async_add_entities)

    device_entities = added[0]
    schedule_entity = next(
        e for e in device_entities if e.entity_description.key == "schedule_status"
    )
    assert schedule_entity.unique_id == f"{mac_id}_schedule_status"
    assert schedule_entity.entity_category is EntityCategory.DIAGNOSTIC
    assert schedule_entity.native_value == "Resume"
