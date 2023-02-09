"""Test run history."""

from datetime import timedelta

from homeassistant.components import recorder
from homeassistant.components.recorder.db_schema import RecorderRuns
from homeassistant.components.recorder.models import process_timestamp
from homeassistant.core import HomeAssistant
from homeassistant.helpers import recorder as recorder_helper
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .common import async_wait_recording_done


async def test_run_history(recorder_mock, hass):
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
        instance.run_history.load_from_db(session)

    assert (
        process_timestamp(
            instance.run_history.get(three_days_ago + timedelta(microseconds=1)).start
        )
        == three_days_ago
    )
    assert (
        process_timestamp(
            instance.run_history.get(two_days_ago + timedelta(microseconds=1)).start
        )
        == two_days_ago
    )
    assert (
        process_timestamp(
            instance.run_history.get(one_day_ago + timedelta(microseconds=1)).start
        )
        == one_day_ago
    )
    assert (
        process_timestamp(instance.run_history.get(now).start)
        == instance.run_history.recording_start
    )


async def test_run_history_while_recorder_is_not_yet_started(
    recorder_db_url: str, hass: HomeAssistant
) -> None:
    """Test the run history while recorder is not yet started.

    This usually happens during schema migration because
    we do not start right away.
    """
    recorder_helper.async_initialize_recorder(hass)
    await async_setup_component(
        hass, "recorder", {"recorder": {"db_url": recorder_db_url}}
    )
    instance = recorder.get_instance(hass)
    run_history = instance.run_history
    assert run_history.current.start == run_history.recording_start
    await async_wait_recording_done(hass)
    assert run_history.current.start == run_history.recording_start
    assert run_history.current.created >= run_history.recording_start
