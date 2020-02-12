"""The lock tests for the august platform."""

import datetime
from unittest.mock import MagicMock

from august.activity import (
    ACTION_LOCK_LOCK,
    ACTION_LOCK_ONETOUCHLOCK,
    ACTION_LOCK_UNLOCK,
)
from august.lock import LockStatus

from homeassistant.components.august.lock import AugustLock
from homeassistant.util import dt

from tests.components.august.mocks import (
    MockActivity,
    MockAugustData,
    _mock_august_lock,
)


class MockAugustLock(AugustLock):
    """A mock for august component AugustLock class."""

    def __init__(self, august_data=None):
        """Init the mock for august component AugustLock class."""
        self._data = august_data
        self._lock = _mock_august_lock()

    @property
    def device_id(self):
        """Mock device_id."""
        return "mockdeviceid1"

    def _update_lock_status(self, lock_status, activity_start_time_utc):
        """Mock updating the lock status."""
        self._data.set_last_lock_status_update_time_utc(
            self._lock.device_id, activity_start_time_utc
        )
        self.last_update_lock_status = {}
        self.last_update_lock_status["lock_status"] = lock_status
        self.last_update_lock_status[
            "activity_start_time_utc"
        ] = activity_start_time_utc
        return MagicMock()


def test__sync_lock_activity_locked_via_onetouchlock():
    """Test _sync_lock_activity locking."""
    data = MockAugustData(last_lock_status_update_timestamp=1)
    lock = MockAugustLock(august_data=data)
    lock_activity_start_timestamp = 1234
    lock_activity = MockActivity(
        action=ACTION_LOCK_ONETOUCHLOCK,
        activity_start_timestamp=lock_activity_start_timestamp,
        activity_end_timestamp=5678,
    )
    lock._sync_lock_activity(lock_activity)
    assert lock.last_update_lock_status["lock_status"] == LockStatus.LOCKED
    assert lock.last_update_lock_status["activity_start_time_utc"] == dt.as_utc(
        datetime.datetime.fromtimestamp(lock_activity_start_timestamp)
    )


def test__sync_lock_activity_locked_via_lock():
    """Test _sync_lock_activity locking."""
    data = MockAugustData(last_lock_status_update_timestamp=1)
    lock = MockAugustLock(august_data=data)
    lock_activity_start_timestamp = 1234
    lock_activity = MockActivity(
        action=ACTION_LOCK_LOCK,
        activity_start_timestamp=lock_activity_start_timestamp,
        activity_end_timestamp=5678,
    )
    lock._sync_lock_activity(lock_activity)
    assert lock.last_update_lock_status["lock_status"] == LockStatus.LOCKED
    assert lock.last_update_lock_status["activity_start_time_utc"] == dt.as_utc(
        datetime.datetime.fromtimestamp(lock_activity_start_timestamp)
    )


def test__sync_lock_activity_unlocked():
    """Test _sync_lock_activity unlocking."""
    data = MockAugustData(last_lock_status_update_timestamp=1)
    lock = MockAugustLock(august_data=data)
    lock_activity_timestamp = 1234
    lock_activity = MockActivity(
        action=ACTION_LOCK_UNLOCK,
        activity_start_timestamp=lock_activity_timestamp,
        activity_end_timestamp=lock_activity_timestamp,
    )
    lock._sync_lock_activity(lock_activity)
    assert lock.last_update_lock_status["lock_status"] == LockStatus.UNLOCKED
    assert lock.last_update_lock_status["activity_start_time_utc"] == dt.as_utc(
        datetime.datetime.fromtimestamp(lock_activity_timestamp)
    )


def test__sync_lock_activity_ignores_old_data():
    """Test _sync_lock_activity unlocking."""
    data = MockAugustData(last_lock_status_update_timestamp=1)
    lock = MockAugustLock(august_data=data)
    first_lock_activity_timestamp = 1234
    lock_activity = MockActivity(
        action=ACTION_LOCK_UNLOCK,
        activity_start_timestamp=first_lock_activity_timestamp,
        activity_end_timestamp=first_lock_activity_timestamp,
    )
    lock._sync_lock_activity(lock_activity)
    assert lock.last_update_lock_status["lock_status"] == LockStatus.UNLOCKED
    assert lock.last_update_lock_status["activity_start_time_utc"] == dt.as_utc(
        datetime.datetime.fromtimestamp(first_lock_activity_timestamp)
    )

    # Now we do the update with an older start time to
    # make sure it ignored
    data.set_last_lock_status_update_time_utc(
        lock.device_id, dt.as_utc(datetime.datetime.fromtimestamp(1000))
    )
    lock_activity_timestamp = 2
    lock_activity = MockActivity(
        action=ACTION_LOCK_LOCK,
        activity_start_timestamp=lock_activity_timestamp,
        activity_end_timestamp=lock_activity_timestamp,
    )
    lock._sync_lock_activity(lock_activity)
    assert lock.last_update_lock_status["lock_status"] == LockStatus.UNLOCKED
    assert lock.last_update_lock_status["activity_start_time_utc"] == dt.as_utc(
        datetime.datetime.fromtimestamp(first_lock_activity_timestamp)
    )
