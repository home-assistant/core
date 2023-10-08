"""The tests for sensor recorder platform can catch up."""
from datetime import datetime, timedelta
from pathlib import Path

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.recorder import SQLITE_URL_PREFIX
from homeassistant.components.recorder.history import get_significant_states
from homeassistant.components.recorder.statistics import (
    get_latest_short_term_statistics,
    statistics_during_period,
)
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers import recorder as recorder_helper
from homeassistant.setup import setup_component
import homeassistant.util.dt as dt_util

from tests.common import get_test_home_assistant
from tests.components.recorder.common import do_adhoc_statistics, wait_recording_done

POWER_SENSOR_ATTRIBUTES = {
    "device_class": "power",
    "state_class": "measurement",
    "unit_of_measurement": "kW",
}


def test_compile_missing_statistics(
    caplog: pytest.LogCaptureFixture, freezer: FrozenDateTimeFactory, tmp_path: Path
) -> None:
    """Test compile missing statistics."""
    test_dir = tmp_path.joinpath("sqlite")
    test_dir.mkdir()
    test_db_file = test_dir.joinpath("test_run_info.db")
    dburl = f"{SQLITE_URL_PREFIX}//{test_db_file}"
    three_days_ago = datetime(2021, 1, 1, 0, 0, 0, tzinfo=dt_util.UTC)
    start_time = three_days_ago + timedelta(days=3)
    freezer.move_to(three_days_ago)
    hass: HomeAssistant = get_test_home_assistant()
    hass.state = CoreState.not_running
    recorder_helper.async_initialize_recorder(hass)
    setup_component(hass, "sensor", {})
    setup_component(hass, "recorder", {"recorder": {"db_url": dburl}})
    hass.start()
    wait_recording_done(hass)
    wait_recording_done(hass)

    hass.states.set("sensor.test1", "0", POWER_SENSOR_ATTRIBUTES)
    wait_recording_done(hass)

    two_days_ago = three_days_ago + timedelta(days=1)
    freezer.move_to(two_days_ago)
    do_adhoc_statistics(hass, start=two_days_ago)
    wait_recording_done(hass)

    latest = get_latest_short_term_statistics(hass, {"sensor.test1"}, {"state", "sum"})
    latest_stat = latest["sensor.test1"][0]
    assert latest_stat["start"] == 1609545600.0
    assert latest_stat["end"] == 1609545600.0 + 300
    count = 1
    past_time = two_days_ago
    while past_time < start_time:
        freezer.move_to(past_time)
        hass.states.set("sensor.test1", str(count), POWER_SENSOR_ATTRIBUTES)
        past_time += timedelta(minutes=5)
        count += 1

    wait_recording_done(hass)

    states = get_significant_states(hass, three_days_ago, past_time, ["sensor.test1"])
    assert len(states["sensor.test1"]) == 576

    hass.stop()
    freezer.move_to(start_time)
    hass: HomeAssistant = get_test_home_assistant()
    hass.state = CoreState.not_running
    recorder_helper.async_initialize_recorder(hass)
    setup_component(hass, "sensor", {})
    setup_component(hass, "recorder", {"recorder": {"db_url": dburl}})
    hass.start()
    wait_recording_done(hass)
    wait_recording_done(hass)

    latest = get_latest_short_term_statistics(hass, {"sensor.test1"}, {"state", "sum"})
    latest_stat = latest["sensor.test1"][0]
    assert latest_stat["start"] == 1609545600.0
    assert latest_stat["end"] == 1609545600.0 + 300

    stats = statistics_during_period(
        hass,
        two_days_ago,
        None,
        units=None,
        statistic_ids={"sensor.test1"},
        period="5minute",
        types={"state", "sum"},
    )
    assert stats is not None
    hass.stop()
