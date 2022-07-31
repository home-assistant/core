"""Test run history."""

from datetime import timedelta

from homeassistant.components import recorder
from homeassistant.components.recorder.db_schema import RecorderRuns
from homeassistant.components.recorder.models import process_timestamp
from homeassistant.util import dt as dt_util


async def test_run_history(hass, recorder_mock):
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
