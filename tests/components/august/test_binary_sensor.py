"""The lock tests for the august platform."""

import datetime
from unittest.mock import MagicMock

from august.activity import ACTION_DOOR_CLOSED, ACTION_DOOR_OPEN
from august.lock import LockDoorStatus

from homeassistant.components.august.binary_sensor import AugustDoorBinarySensor
from homeassistant.util import dt

from tests.components.august.mocks import (
    MockActivity,
    MockAugustData,
    _mock_august_lock,
)


class MockAugustDoorBinarySensor(AugustDoorBinarySensor):
    """A mock for august component AugustLock class."""

    def __init__(self, august_data=None):
        """Init the mock for august component AugustLock class."""
        self._data = august_data
        self._door = _mock_august_lock()

    @property
    def name(self):
        """Mock name."""
        return "mockedname1"

    @property
    def device_id(self):
        """Mock device_id."""
        return "mockdeviceid1"

    def _update_door_state(self, door_state, activity_start_time_utc):
        """Mock updating the lock status."""
        self._data.set_last_door_state_update_time_utc(
            self._door.device_id, activity_start_time_utc
        )
        self.last_update_door_state = {}
        self.last_update_door_state["door_state"] = door_state
        self.last_update_door_state["activity_start_time_utc"] = activity_start_time_utc
        return MagicMock()


def test__sync_door_activity_doored_via_dooropen():
    """Test _sync_door_activity dooropen."""
    data = MockAugustData(last_door_state_update_timestamp=1)
    door = MockAugustDoorBinarySensor(august_data=data)
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
    data = MockAugustData(last_door_state_update_timestamp=1)
    door = MockAugustDoorBinarySensor(august_data=data)
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
    data = MockAugustData(last_door_state_update_timestamp=1)
    door = MockAugustDoorBinarySensor(august_data=data)
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
        door.device_id, dt.as_utc(datetime.datetime.fromtimestamp(1000))
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
