"""The lock tests for the august platform."""

import datetime

from august.activity import ACTION_DOOR_CLOSED, ACTION_DOOR_OPEN
from august.lock import LockDoorStatus

from homeassistant.util import dt

from tests.components.august.mocks import (
    MockActivity,
    MockAugustComponentData,
    MockAugustComponentDoorBinarySensor,
    _mock_august_lock,
)


def test__sync_door_activity_doored_via_dooropen():
    """Test _sync_door_activity dooropen."""
    data = MockAugustComponentData(last_door_state_update_timestamp=1)
    lock = _mock_august_lock()
    data.set_mocked_locks([lock])
    door = MockAugustComponentDoorBinarySensor(data, "door_open", lock)
    door_activity_start_timestamp = 1234
    door_activity = MockActivity(
        action=ACTION_DOOR_OPEN,
        activity_start_timestamp=door_activity_start_timestamp,
        activity_end_timestamp=5678,
    )
    door._sync_door_activity(door_activity)
    assert door.last_update_door_state["door_state"] == LockDoorStatus.OPEN
    assert door.last_update_door_state["activity_start_time_utc"] == dt.as_utc(
        datetime.datetime.fromtimestamp(door_activity_start_timestamp)
    )


def test__sync_door_activity_doorclosed():
    """Test _sync_door_activity doorclosed."""
    data = MockAugustComponentData(last_door_state_update_timestamp=1)
    lock = _mock_august_lock()
    data.set_mocked_locks([lock])
    door = MockAugustComponentDoorBinarySensor(data, "door_open", lock)
    door_activity_timestamp = 1234
    door_activity = MockActivity(
        action=ACTION_DOOR_CLOSED,
        activity_start_timestamp=door_activity_timestamp,
        activity_end_timestamp=door_activity_timestamp,
    )
    door._sync_door_activity(door_activity)
    assert door.last_update_door_state["door_state"] == LockDoorStatus.CLOSED
    assert door.last_update_door_state["activity_start_time_utc"] == dt.as_utc(
        datetime.datetime.fromtimestamp(door_activity_timestamp)
    )


def test__sync_door_activity_ignores_old_data():
    """Test _sync_door_activity dooropen then expired doorclosed."""
    data = MockAugustComponentData(last_door_state_update_timestamp=1)
    lock = _mock_august_lock()
    data.set_mocked_locks([lock])
    door = MockAugustComponentDoorBinarySensor(data, "door_open", lock)
    first_door_activity_timestamp = 1234
    door_activity = MockActivity(
        action=ACTION_DOOR_OPEN,
        activity_start_timestamp=first_door_activity_timestamp,
        activity_end_timestamp=first_door_activity_timestamp,
    )
    door._sync_door_activity(door_activity)
    assert door.last_update_door_state["door_state"] == LockDoorStatus.OPEN
    assert door.last_update_door_state["activity_start_time_utc"] == dt.as_utc(
        datetime.datetime.fromtimestamp(first_door_activity_timestamp)
    )

    # Now we do the update with an older start time to
    # make sure it ignored
    data.set_last_door_state_update_time_utc(
        lock.device_id, dt.as_utc(datetime.datetime.fromtimestamp(1000))
    )
    door_activity_timestamp = 2
    door_activity = MockActivity(
        action=ACTION_DOOR_CLOSED,
        activity_start_timestamp=door_activity_timestamp,
        activity_end_timestamp=door_activity_timestamp,
    )
    door._sync_door_activity(door_activity)
    assert door.last_update_door_state["door_state"] == LockDoorStatus.OPEN
    assert door.last_update_door_state["activity_start_time_utc"] == dt.as_utc(
        datetime.datetime.fromtimestamp(first_door_activity_timestamp)
    )
