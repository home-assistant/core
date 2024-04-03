"""Test recorder runs table manager."""

from datetime import timedelta
from unittest.mock import patch

from homeassistant.components import recorder
from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.db_schema import RecorderRuns
from homeassistant.components.recorder.models import process_timestamp
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.typing import RecorderInstanceGenerator


async def test_run_history(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """Test the run history gives the correct run."""
    instance = recorder.get_instance(hass)
    now = dt_util.utcnow()
    three_days_ago = now - timedelta(days=3)
    two_days_ago = now - timedelta(days=2)
    one_day_ago = now - timedelta(days=1)

    with instance.get_session() as session:
        session.add(RecorderRuns(start=three_days_ago, created=three_days_ago))
        session.add(RecorderRuns(start=two_days_ago, created=two_days_ago))
        session.add(RecorderRuns(start=one_day_ago, created=one_day_ago))
        session.commit()
        instance.recorder_runs_manager.load_from_db(session)

    assert (
        process_timestamp(
            instance.recorder_runs_manager.get(
                three_days_ago + timedelta(microseconds=1)
            ).start
        )
        == three_days_ago
    )
    assert (
        process_timestamp(
            instance.recorder_runs_manager.get(
                two_days_ago + timedelta(microseconds=1)
            ).start
        )
        == two_days_ago
    )
    assert (
        process_timestamp(
            instance.recorder_runs_manager.get(
                one_day_ago + timedelta(microseconds=1)
            ).start
        )
        == one_day_ago
    )
    assert (
        process_timestamp(instance.recorder_runs_manager.get(now).start)
        == instance.recorder_runs_manager.recording_start
    )


async def test_run_history_while_recorder_is_not_yet_started(
    async_setup_recorder_instance: RecorderInstanceGenerator,
    hass: HomeAssistant,
    recorder_db_url: str,
) -> None:
    """Test the run history while recorder is not yet started.

    This usually happens during schema migration because
    we do not start right away.
    """
    # Prevent the run history from starting to ensure
    # we can test run_history.current.start returns the expected value
    with patch(
        "homeassistant.components.recorder.table_managers.recorder_runs.RecorderRunsManager.start",
    ):
        instance = await async_setup_recorder_instance(hass)
    run_history = instance.recorder_runs_manager
    assert run_history.current.start == run_history.recording_start

    def _start_run_history():
        with instance.get_session() as session:
            run_history.start(session)

    # Ideally we would run run_history.start in the recorder thread
    # but since we mocked it out above, we run it directly here
    # via the database executor to avoid blocking the event loop.
    await instance.async_add_executor_job(_start_run_history)
    assert run_history.current.start == run_history.recording_start
    assert run_history.current.created >= run_history.recording_start
