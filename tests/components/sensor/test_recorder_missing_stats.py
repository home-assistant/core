"""The tests for sensor recorder platform can catch up."""
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.recorder.history import get_significant_states
from homeassistant.components.recorder.statistics import (
    get_latest_short_term_statistics_with_session,
    statistics_during_period,
)
from homeassistant.components.recorder.util import session_scope
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers import recorder as recorder_helper
from homeassistant.setup import setup_component
import homeassistant.util.dt as dt_util

from tests.common import get_test_home_assistant
from tests.components.recorder.common import do_adhoc_statistics, wait_recording_done

POWER_SENSOR_ATTRIBUTES = {
    "device_class": "energy",
    "state_class": "measurement",
    "unit_of_measurement": "kWh",
}


@pytest.fixture(autouse=True)
def disable_db_issue_creation():
    """Disable the creation of the database issue."""
    with patch(
        "homeassistant.components.recorder.util._async_create_mariadb_range_index_regression_issue"
    ):
        yield


@pytest.mark.timeout(25)
def test_compile_missing_statistics(
    freezer: FrozenDateTimeFactory, recorder_db_url: str, tmp_path: Path
) -> None:
    """Test compile missing statistics."""
    if recorder_db_url == "sqlite://":
        # On-disk database because we need to stop and start hass
        # and have it persist.
        recorder_db_url = "sqlite:///" + str(tmp_path / "pytest.db")
    config = {
        "db_url": recorder_db_url,
    }
    three_days_ago = datetime(2021, 1, 1, 0, 0, 0, tzinfo=dt_util.UTC)
    start_time = three_days_ago + timedelta(days=3)
    freezer.move_to(three_days_ago)
    hass: HomeAssistant = get_test_home_assistant()
    hass.set_state(CoreState.not_running)
    recorder_helper.async_initialize_recorder(hass)
    setup_component(hass, "sensor", {})
    setup_component(hass, "recorder", {"recorder": config})
    hass.start()
    wait_recording_done(hass)
    wait_recording_done(hass)

    hass.states.set("sensor.test1", "0", POWER_SENSOR_ATTRIBUTES)
    wait_recording_done(hass)

    two_days_ago = three_days_ago + timedelta(days=1)
    freezer.move_to(two_days_ago)
    do_adhoc_statistics(hass, start=two_days_ago)
    wait_recording_done(hass)
    with session_scope(hass=hass, read_only=True) as session:
        latest = get_latest_short_term_statistics_with_session(
            hass, session, {"sensor.test1"}, {"state", "sum"}
        )
    latest_stat = latest["sensor.test1"][0]
    assert latest_stat["start"] == 1609545600.0
    assert latest_stat["end"] == 1609545600.0 + 300
    count = 1
    past_time = two_days_ago
    while past_time <= start_time:
        freezer.move_to(past_time)
        hass.states.set("sensor.test1", str(count), POWER_SENSOR_ATTRIBUTES)
        past_time += timedelta(minutes=5)
        count += 1

    wait_recording_done(hass)

    states = get_significant_states(hass, three_days_ago, past_time, ["sensor.test1"])
    assert len(states["sensor.test1"]) == 577

    hass.stop()
    freezer.move_to(start_time)
    hass: HomeAssistant = get_test_home_assistant()
    hass.set_state(CoreState.not_running)
    recorder_helper.async_initialize_recorder(hass)
    setup_component(hass, "sensor", {})
    hass.states.set("sensor.test1", "0", POWER_SENSOR_ATTRIBUTES)
    setup_component(hass, "recorder", {"recorder": config})
    hass.start()
    wait_recording_done(hass)
    wait_recording_done(hass)
    with session_scope(hass=hass, read_only=True) as session:
        latest = get_latest_short_term_statistics_with_session(
            hass, session, {"sensor.test1"}, {"state", "sum", "max", "mean", "min"}
        )
    latest_stat = latest["sensor.test1"][0]
    assert latest_stat["start"] == 1609718100.0
    assert latest_stat["end"] == 1609718100.0 + 300
    assert latest_stat["mean"] == 576.0
    assert latest_stat["min"] == 575.0
    assert latest_stat["max"] == 576.0
    stats = statistics_during_period(
        hass,
        two_days_ago,
        start_time,
        units={"energy": "kWh"},
        statistic_ids={"sensor.test1"},
        period="hour",
        types={"mean"},
    )
    # Make sure we have 48 hours of statistics
    assert len(stats["sensor.test1"]) == 48
    # Make sure the last mean is 570.5
    assert stats["sensor.test1"][-1]["mean"] == 570.5
    hass.stop()
