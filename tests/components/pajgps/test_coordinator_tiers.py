"""Tests for the three update tiers (devices, positions+sensors, notifications) and the alert-toggle write path (async_update_alert_state)."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

from pajgps_api.pajgps_api_error import PajGpsApiError

from homeassistant.components.pajgps.coordinator import CoordinatorData

from .test_common import make_coordinator, make_device, make_trackpoint

# ---------------------------------------------------------------------------
# Devices tier
# ---------------------------------------------------------------------------


async def test_devices_stored_in_snapshot() -> None:
    """Test that fetched devices are stored in the coordinator snapshot."""
    coord = make_coordinator()
    devices = [make_device(1), make_device(2)]
    coord.api.get_devices = AsyncMock(return_value=devices)

    received = []
    coord.async_set_updated_data = received.append

    await coord._run_devices_tier()

    assert len(received) == 1
    assert received[0].devices == devices


async def test_api_error_preserves_stale_data() -> None:
    """Test that a devices API error leaves existing coordinator data unchanged."""
    coord = make_coordinator()
    coord.data = CoordinatorData(devices=[make_device(1)])
    coord.api.get_devices = AsyncMock(side_effect=PajGpsApiError("fail"))

    received = []
    coord.async_set_updated_data = received.append

    await coord._run_devices_tier()

    # async_set_updated_data should NOT have been called
    assert len(received) == 0
    # Existing data unchanged
    assert len(coord.data.devices) == 1


async def test_timestamp_updated_even_on_error() -> None:
    """Test that the last-fetch timestamp is updated even when the API call fails."""
    coord = make_coordinator()
    coord.api.get_devices = AsyncMock(side_effect=PajGpsApiError("fail"))
    coord.async_set_updated_data = MagicMock()

    before = time.monotonic()
    await coord._run_devices_tier()
    assert coord._last_devices_fetch >= before


# ---------------------------------------------------------------------------
# Positions tier helpers
# ---------------------------------------------------------------------------


async def _coord_with_device(device_id: int = 1, **entry_kwargs):  # type: ignore[return]
    """Create a coordinator pre-populated with one device and mocked API responses."""
    coord = make_coordinator(**entry_kwargs)
    coord.data = CoordinatorData(devices=[make_device(device_id)])
    coord.api.get_all_last_positions = AsyncMock(
        return_value=[make_trackpoint(device_id)]
    )
    return coord


# ---------------------------------------------------------------------------
# Positions tier
# ---------------------------------------------------------------------------


async def test_positions_pushed_immediately() -> None:
    """Test that position data is pushed to the snapshot after a positions tier run."""
    coord = await _coord_with_device(1)

    snapshots = []
    coord.async_set_updated_data = snapshots.append

    await coord._run_positions_tier()

    # First snapshot should have positions
    assert any(1 in s.positions for s in snapshots)


async def test_position_api_error_does_not_push() -> None:
    """Test that a positions API error prevents any snapshot from being pushed."""
    coord = make_coordinator()
    coord.data = CoordinatorData(devices=[make_device(1)])
    coord.api.get_all_last_positions = AsyncMock(side_effect=PajGpsApiError("fail"))

    received = []
    coord.async_set_updated_data = received.append

    await coord._run_positions_tier()

    assert len(received) == 0


async def test_no_devices_exits_early() -> None:
    """Test that the positions tier exits early when there are no devices."""
    coord = make_coordinator()
    coord.data = CoordinatorData(devices=[])
    coord.api.get_all_last_positions = AsyncMock()

    await coord._run_positions_tier()

    coord.api.get_all_last_positions.assert_not_awaited()
