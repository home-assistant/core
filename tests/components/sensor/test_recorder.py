"""The tests for sensor recorder platform."""
# pylint: disable=protected-access,invalid-name
from datetime import timedelta
from unittest.mock import patch, sentinel

import pytest

from homeassistant.components.recorder import history
from homeassistant.components.recorder.const import DATA_INSTANCE
from homeassistant.components.recorder.models import process_timestamp_to_utc_isoformat
from homeassistant.components.recorder.statistics import statistics_during_period
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.setup import setup_component
import homeassistant.util.dt as dt_util

from tests.common import get_test_home_assistant, init_recorder_component
from tests.components.recorder.common import wait_recording_done


@pytest.fixture
def hass_recorder():
    """Home Assistant fixture with in-memory recorder."""
    hass = get_test_home_assistant()

    def setup_recorder(config=None):
        """Set up with params."""
        init_recorder_component(hass, config)
        hass.start()
        hass.block_till_done()
        hass.data[DATA_INSTANCE].block_till_done()
        return hass

    yield setup_recorder
    hass.stop()


def test_compile_hourly_statistics(hass_recorder):
    """Test compiling hourly statistics."""
    hass = hass_recorder()
    recorder = hass.data[DATA_INSTANCE]
    setup_component(hass, "sensor", {})
    zero, four, states = record_states(hass)
    hist = history.get_significant_states(hass, zero, four)
    assert dict(states) == dict(hist)

    recorder.do_adhoc_statistics(period="hourly", start=zero)
    wait_recording_done(hass)
    stats = statistics_during_period(hass, zero)
    assert stats == {
        "sensor.test1": [
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(zero),
                "mean": 15.0,
                "min": 10.0,
                "max": 20.0,
                "last_reset": None,
                "abs_value": None,
                "sum": None,
            }
        ]
    }


def test_compile_hourly_energy_statistics(hass_recorder):
    """Test compiling hourly statistics."""
    hass = hass_recorder()
    recorder = hass.data[DATA_INSTANCE]
    setup_component(hass, "sensor", {})
    zero, four, eight, states = record_energy_states(hass)
    hist = history.get_significant_states(
        hass, zero - timedelta.resolution, eight + timedelta.resolution
    )
    assert dict(states)["sensor.test1"] == dict(hist)["sensor.test1"]

    recorder.do_adhoc_statistics(period="hourly", start=zero)
    wait_recording_done(hass)
    recorder.do_adhoc_statistics(period="hourly", start=zero + timedelta(hours=1))
    wait_recording_done(hass)
    recorder.do_adhoc_statistics(period="hourly", start=zero + timedelta(hours=2))
    wait_recording_done(hass)
    stats = statistics_during_period(hass, zero)
    assert stats == {
        "sensor.test1": [
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(zero),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": process_timestamp_to_utc_isoformat(zero),
                "abs_value": 20.0,
                "sum": 10.0,
            },
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(zero + timedelta(hours=1)),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": process_timestamp_to_utc_isoformat(four),
                "abs_value": 40.0,
                "sum": 10.0,
            },
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(zero + timedelta(hours=2)),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": process_timestamp_to_utc_isoformat(four),
                "abs_value": 70.0,
                "sum": 40.0,
            },
        ]
    }


def test_compile_hourly_statistics_unchanged(hass_recorder):
    """Test compiling hourly statistics, with no changes during the hour."""
    hass = hass_recorder()
    recorder = hass.data[DATA_INSTANCE]
    setup_component(hass, "sensor", {})
    zero, four, states = record_states(hass)
    hist = history.get_significant_states(hass, zero, four)
    assert dict(states) == dict(hist)

    recorder.do_adhoc_statistics(period="hourly", start=four)
    wait_recording_done(hass)
    stats = statistics_during_period(hass, four)
    assert stats == {
        "sensor.test1": [
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(four),
                "mean": 20.0,
                "min": 20.0,
                "max": 20.0,
                "last_reset": None,
                "abs_value": None,
                "sum": None,
            }
        ]
    }


def test_compile_hourly_statistics_partially_unavailable(hass_recorder):
    """Test compiling hourly statistics, with the sensor being partially unavailable."""
    hass = hass_recorder()
    recorder = hass.data[DATA_INSTANCE]
    setup_component(hass, "sensor", {})
    zero, four, states = record_states_partially_unavailable(hass)
    hist = history.get_significant_states(hass, zero, four)
    assert dict(states) == dict(hist)

    recorder.do_adhoc_statistics(period="hourly", start=zero)
    wait_recording_done(hass)
    stats = statistics_during_period(hass, zero)
    assert stats == {
        "sensor.test1": [
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(zero),
                "mean": 17.5,
                "min": 10.0,
                "max": 25.0,
                "last_reset": None,
                "abs_value": None,
                "sum": None,
            }
        ]
    }


def test_compile_hourly_statistics_unavailable(hass_recorder):
    """Test compiling hourly statistics, with the sensor being unavailable."""
    hass = hass_recorder()
    recorder = hass.data[DATA_INSTANCE]
    setup_component(hass, "sensor", {})
    zero, four, states = record_states_partially_unavailable(hass)
    hist = history.get_significant_states(hass, zero, four)
    assert dict(states) == dict(hist)

    recorder.do_adhoc_statistics(period="hourly", start=four)
    wait_recording_done(hass)
    stats = statistics_during_period(hass, four)
    assert stats == {}


def record_states(hass):
    """Record some test states.

    We inject a bunch of state updates for temperature sensors.
    """
    mp = "media_player.test"
    sns1 = "sensor.test1"
    sns2 = "sensor.test2"
    sns3 = "sensor.test3"
    sns1_attr = {"device_class": "temperature", "state_class": "measurement"}
    sns2_attr = {"device_class": "temperature"}
    sns3_attr = {}

    def set_state(entity_id, state, **kwargs):
        """Set the state."""
        hass.states.set(entity_id, state, **kwargs)
        wait_recording_done(hass)
        return hass.states.get(entity_id)

    zero = dt_util.utcnow()
    one = zero + timedelta(minutes=1)
    two = one + timedelta(minutes=15)
    three = two + timedelta(minutes=30)
    four = three + timedelta(minutes=15)

    states = {mp: [], sns1: [], sns2: [], sns3: []}
    with patch("homeassistant.components.recorder.dt_util.utcnow", return_value=one):
        states[mp].append(
            set_state(mp, "idle", attributes={"media_title": str(sentinel.mt1)})
        )
        states[mp].append(
            set_state(mp, "YouTube", attributes={"media_title": str(sentinel.mt2)})
        )
        states[sns1].append(set_state(sns1, "10", attributes=sns1_attr))
        states[sns2].append(set_state(sns2, "10", attributes=sns2_attr))
        states[sns3].append(set_state(sns3, "10", attributes=sns3_attr))

    with patch("homeassistant.components.recorder.dt_util.utcnow", return_value=two):
        states[sns1].append(set_state(sns1, "15", attributes=sns1_attr))
        states[sns2].append(set_state(sns2, "15", attributes=sns2_attr))
        states[sns3].append(set_state(sns3, "15", attributes=sns3_attr))

    with patch("homeassistant.components.recorder.dt_util.utcnow", return_value=three):
        states[sns1].append(set_state(sns1, "20", attributes=sns1_attr))
        states[sns2].append(set_state(sns2, "20", attributes=sns2_attr))
        states[sns3].append(set_state(sns3, "20", attributes=sns3_attr))

    return zero, four, states


def record_energy_states(hass):
    """Record some test states.

    We inject a bunch of state updates for energy sensors.
    """
    sns1 = "sensor.test1"
    sns2 = "sensor.test2"
    sns3 = "sensor.test3"
    sns1_attr = {"device_class": "energy", "state_class": "measurement"}
    sns2_attr = {"device_class": "energy"}
    sns3_attr = {}

    def set_state(entity_id, state, **kwargs):
        """Set the state."""
        hass.states.set(entity_id, state, **kwargs)
        wait_recording_done(hass)
        return hass.states.get(entity_id)

    zero = dt_util.utcnow()
    one = zero + timedelta(minutes=15)
    two = one + timedelta(minutes=30)
    three = two + timedelta(minutes=15)
    four = three + timedelta(minutes=15)
    five = four + timedelta(minutes=30)
    six = five + timedelta(minutes=15)
    seven = six + timedelta(minutes=15)
    eight = seven + timedelta(minutes=30)

    sns1_attr = {
        "device_class": "energy",
        "state_class": "measurement",
        "last_reset": zero.isoformat(),
    }
    sns2_attr = {"device_class": "energy"}
    sns3_attr = {}

    states = {sns1: [], sns2: [], sns3: []}
    with patch("homeassistant.components.recorder.dt_util.utcnow", return_value=zero):
        states[sns1].append(set_state(sns1, "10", attributes=sns1_attr))  # Sum 0
        states[sns2].append(set_state(sns2, "10", attributes=sns2_attr))
        states[sns3].append(set_state(sns3, "10", attributes=sns3_attr))

    with patch("homeassistant.components.recorder.dt_util.utcnow", return_value=one):
        states[sns1].append(set_state(sns1, "15", attributes=sns1_attr))  # Sum 5

    with patch("homeassistant.components.recorder.dt_util.utcnow", return_value=two):
        states[sns1].append(set_state(sns1, "20", attributes=sns1_attr))  # Sum 10

    with patch("homeassistant.components.recorder.dt_util.utcnow", return_value=three):
        states[sns1].append(set_state(sns1, "10", attributes=sns1_attr))  # Sum 0

    sns1_attr = {
        "device_class": "energy",
        "state_class": "measurement",
        "last_reset": four.isoformat(),
    }
    with patch("homeassistant.components.recorder.dt_util.utcnow", return_value=four):
        states[sns1].append(set_state(sns1, "30", attributes=sns1_attr))  # Sum 0

    with patch("homeassistant.components.recorder.dt_util.utcnow", return_value=five):
        states[sns1].append(set_state(sns1, "40", attributes=sns1_attr))  # Sum 10

    with patch("homeassistant.components.recorder.dt_util.utcnow", return_value=six):
        states[sns1].append(set_state(sns1, "50", attributes=sns1_attr))  # Sum 20

    with patch("homeassistant.components.recorder.dt_util.utcnow", return_value=seven):
        states[sns1].append(set_state(sns1, "60", attributes=sns1_attr))  # Sum 30

    with patch("homeassistant.components.recorder.dt_util.utcnow", return_value=eight):
        states[sns1].append(set_state(sns1, "70", attributes=sns1_attr))  # Sum 40

    return zero, four, eight, states


def record_states_partially_unavailable(hass):
    """Record some test states.

    We inject a bunch of state updates temperature sensors.
    """
    mp = "media_player.test"
    sns1 = "sensor.test1"
    sns2 = "sensor.test2"
    sns3 = "sensor.test3"
    sns1_attr = {"device_class": "temperature", "state_class": "measurement"}
    sns2_attr = {"device_class": "temperature"}
    sns3_attr = {}

    def set_state(entity_id, state, **kwargs):
        """Set the state."""
        hass.states.set(entity_id, state, **kwargs)
        wait_recording_done(hass)
        return hass.states.get(entity_id)

    zero = dt_util.utcnow()
    one = zero + timedelta(minutes=1)
    two = one + timedelta(minutes=15)
    three = two + timedelta(minutes=30)
    four = three + timedelta(minutes=15)

    states = {mp: [], sns1: [], sns2: [], sns3: []}
    with patch("homeassistant.components.recorder.dt_util.utcnow", return_value=one):
        states[mp].append(
            set_state(mp, "idle", attributes={"media_title": str(sentinel.mt1)})
        )
        states[mp].append(
            set_state(mp, "YouTube", attributes={"media_title": str(sentinel.mt2)})
        )
        states[sns1].append(set_state(sns1, "10", attributes=sns1_attr))
        states[sns2].append(set_state(sns2, "10", attributes=sns2_attr))
        states[sns3].append(set_state(sns3, "10", attributes=sns3_attr))

    with patch("homeassistant.components.recorder.dt_util.utcnow", return_value=two):
        states[sns1].append(set_state(sns1, "25", attributes=sns1_attr))
        states[sns2].append(set_state(sns2, "25", attributes=sns2_attr))
        states[sns3].append(set_state(sns3, "25", attributes=sns3_attr))

    with patch("homeassistant.components.recorder.dt_util.utcnow", return_value=three):
        states[sns1].append(set_state(sns1, STATE_UNAVAILABLE, attributes=sns1_attr))
        states[sns2].append(set_state(sns2, STATE_UNAVAILABLE, attributes=sns2_attr))
        states[sns3].append(set_state(sns3, STATE_UNAVAILABLE, attributes=sns3_attr))

    return zero, four, states
