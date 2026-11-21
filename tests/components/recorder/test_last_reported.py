"""Tests for writing the last reported timestamp of states."""

from dataclasses import dataclass
from typing import override

import pytest
from pytest_homeassistant.components.recorder.common import (
    async_recorder_block_till_done,
    async_wait_recording_done,
)
from pytest_homeassistant.typing import RecorderInstanceContextManager
from sqlalchemy import select

from homeassistant.components.recorder import Recorder, get_instance
from homeassistant.components.recorder.db_schema import States
from homeassistant.components.recorder.table_managers.states import StatesManager
from homeassistant.components.recorder.tasks import CommitTask, RecorderTask
from homeassistant.components.recorder.util import session_scope
from homeassistant.core import HomeAssistant

MISSING_STATE_ID = 999_999


@pytest.fixture
async def mock_recorder_before_hass(
    async_test_recorder: RecorderInstanceContextManager,
) -> None:
    """Set up recorder."""


@dataclass(slots=True)
class _QueueLastReportedTask(RecorderTask):
    """Queue last reported timestamps as if newer states had been recorded."""

    timestamps: dict[int, float]
    commit_before = False

    @override
    def run(self, instance: Recorder) -> None:
        for state_id, timestamp in self.timestamps.items():
            instance.states_manager.update_pending_last_reported(state_id, timestamp)
        instance._event_session_has_pending_writes = True


async def test_last_reported_of_a_deleted_state_is_skipped(
    recorder_mock: Recorder, hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """A last reported timestamp for a state that is gone must not fail the commit.

    The ORM bulk update by primary key raised StaleDataError for it, which failed
    the commit and every commit after it.
    """
    hass.states.async_set("sensor.test", "on")
    await async_wait_recording_done(hass)

    def _state_id() -> int:
        with session_scope(hass=hass, read_only=True) as session:
            return session.execute(select(States.state_id)).scalar_one()

    state_id = await get_instance(hass).async_add_executor_job(_state_id)

    instance = get_instance(hass)
    instance.queue_task(
        _QueueLastReportedTask({state_id: 1234.5, MISSING_STATE_ID: 1234.5})
    )
    instance.queue_task(CommitTask())
    await async_recorder_block_till_done(hass)

    def _last_reported() -> float | None:
        with session_scope(hass=hass, read_only=True) as session:
            return session.execute(
                select(States.last_reported_ts).where(States.state_id == state_id)
            ).scalar_one()

    assert await get_instance(hass).async_add_executor_job(_last_reported) == 1234.5
    assert "StaleDataError" not in caplog.text

    # and the recorder keeps recording
    hass.states.async_set("sensor.test", "off")
    await async_wait_recording_done(hass)

    def _states() -> list[str]:
        with session_scope(hass=hass, read_only=True) as session:
            return list(
                session.execute(
                    select(States.state).order_by(States.state_id)
                ).scalars()
            )

    assert await get_instance(hass).async_add_executor_job(_states) == ["on", "off"]


def test_reset_drops_pending_last_reported() -> None:
    """Closing the event session drops the timestamps it didn't commit."""
    manager = StatesManager()
    manager.update_pending_last_reported(1, 10.0)

    manager.reset()

    assert manager.get_pending_last_reported_timestamp() == {}
