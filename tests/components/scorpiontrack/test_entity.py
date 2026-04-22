"""Test ScorpionTrack entity helpers."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from unittest.mock import patch

from homeassistant.components.scorpiontrack.device_tracker import (
    ScorpionTrackTrackerEntity,
)
from homeassistant.components.scorpiontrack.entity import _bearing_to_cardinal
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import setup_integration

from tests.common import MockConfigEntry


async def test_tracker_helper_methods_handle_removed_vehicle(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_share,
) -> None:
    """Tracker helpers should fall back cleanly when a vehicle disappears."""
    await setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    entity = ScorpionTrackTrackerEntity(coordinator, 1)
    coordinator.async_set_updated_data(replace(mock_share, vehicles=()))
    await hass.async_block_till_done()

    assert entity.name == "AB12 CDE"
    assert entity.latitude is None
    assert entity.longitude is None
    assert entity.position_age() is None

    attributes = entity.common_location_attributes(include_coordinates=True)
    assert attributes["latitude"] is None
    assert attributes["longitude"] is None
    assert attributes["removed_from_share"] is True


async def test_tracker_helper_methods_handle_missing_and_future_timestamps(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_share,
) -> None:
    """Tracker helpers should handle missing and future timestamps."""
    await setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    entity = ScorpionTrackTrackerEntity(coordinator, 1)
    vehicle = mock_share.vehicles[0]

    no_timestamp_vehicle = replace(
        vehicle,
        position=replace(vehicle.position, timestamp=None),
    )
    coordinator.async_set_updated_data(
        replace(mock_share, vehicles=(no_timestamp_vehicle,))
    )
    await hass.async_block_till_done()
    assert entity.position_age() is None

    future_vehicle = replace(
        vehicle,
        position=replace(
            vehicle.position,
            timestamp=dt_util.utcnow() + timedelta(minutes=5),
        ),
    )
    coordinator.async_set_updated_data(replace(mock_share, vehicles=(future_vehicle,)))
    await hass.async_block_till_done()
    assert entity.position_age() == timedelta(0)


def test_bearing_to_cardinal_handles_missing_value() -> None:
    """A missing bearing should not produce a heading."""
    assert _bearing_to_cardinal(None) is None


async def test_common_location_attributes_reuse_computed_age(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Shared attributes should not recompute age/staleness from scratch."""
    await setup_integration(hass, mock_config_entry)

    entity = ScorpionTrackTrackerEntity(mock_config_entry.runtime_data, 1)

    with patch.object(
        entity,
        "position_age",
        wraps=entity.position_age,
    ) as mock_position_age:
        attributes = entity.common_location_attributes()

    assert attributes["stale"] is True
    assert mock_position_age.call_count == 1
