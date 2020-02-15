"""The lock tests for the august platform."""

import datetime

from august.activity import (
    ACTION_LOCK_LOCK,
    ACTION_LOCK_ONETOUCHLOCK,
    ACTION_LOCK_UNLOCK,
)
from august.lock import LockStatus

from homeassistant.util import dt

from tests.components.august.mocks import MockActivity, MockAugustData, MockAugustLock


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
