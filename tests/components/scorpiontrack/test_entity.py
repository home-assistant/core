"""Test ScorpionTrack entity helpers."""

from dataclasses import replace
from datetime import timedelta

from pyscorpiontrack import ScorpionTrackShare

from homeassistant.components.scorpiontrack.device_tracker import (
    ScorpionTrackTrackerEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import setup_integration

from tests.common import MockConfigEntry


async def test_tracker_helper_methods_handle_removed_vehicle(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_share: ScorpionTrackShare,
) -> None:
    """Tracker helpers should fall back cleanly when a vehicle disappears."""
    await setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    entity = ScorpionTrackTrackerEntity(coordinator, 1)
    coordinator.async_set_updated_data(replace(mock_share, vehicles=()))
    await hass.async_block_till_done()

    assert entity.available is False
    assert entity.latitude is None
    assert entity.longitude is None
    assert entity.position_age() is None

    assert entity.device_info["name"] == "AB12 CDE"


async def test_tracker_helper_methods_handle_missing_and_future_timestamps(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_share: ScorpionTrackShare,
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
