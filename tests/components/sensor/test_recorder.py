"""The tests for sensor recorder platform."""
# pylint: disable=protected-access,invalid-name
from datetime import timedelta
from unittest.mock import patch

import pytest
from pytest import approx

from homeassistant.components.recorder import history
from homeassistant.components.recorder.const import DATA_INSTANCE
from homeassistant.components.recorder.models import process_timestamp_to_utc_isoformat
from homeassistant.components.recorder.statistics import (
    get_metadata,
    list_statistic_ids,
    statistics_during_period,
)
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.setup import setup_component
import homeassistant.util.dt as dt_util

from tests.components.recorder.common import wait_recording_done

ENERGY_SENSOR_ATTRIBUTES = {
    "device_class": "energy",
    "state_class": "measurement",
    "unit_of_measurement": "kWh",
}
POWER_SENSOR_ATTRIBUTES = {
    "device_class": "power",
    "state_class": "measurement",
    "unit_of_measurement": "kW",
}
PRESSURE_SENSOR_ATTRIBUTES = {
    "device_class": "pressure",
    "state_class": "measurement",
    "unit_of_measurement": "hPa",
}
TEMPERATURE_SENSOR_ATTRIBUTES = {
    "device_class": "temperature",
    "state_class": "measurement",
    "unit_of_measurement": "°C",
}
GAS_SENSOR_ATTRIBUTES = {
    "device_class": "gas",
    "state_class": "measurement",
    "unit_of_measurement": "m³",
}


@pytest.mark.parametrize(
    "device_class,unit,native_unit,mean,min,max",
    [
        (None, "%", "%", 16.440677, 10, 30),
        ("battery", "%", "%", 16.440677, 10, 30),
        ("battery", None, None, 16.440677, 10, 30),
        ("humidity", "%", "%", 16.440677, 10, 30),
        ("humidity", None, None, 16.440677, 10, 30),
        ("pressure", "Pa", "Pa", 16.440677, 10, 30),
        ("pressure", "hPa", "Pa", 1644.0677, 1000, 3000),
        ("pressure", "mbar", "Pa", 1644.0677, 1000, 3000),
        ("pressure", "inHg", "Pa", 55674.53, 33863.89, 101591.67),
        ("pressure", "psi", "Pa", 113354.48, 68947.57, 206842.71),
        ("temperature", "°C", "°C", 16.440677, 10, 30),
        ("temperature", "°F", "°C", -8.644068, -12.22222, -1.111111),
    ],
)
def test_compile_hourly_statistics(
    hass_recorder, caplog, device_class, unit, native_unit, mean, min, max
):
    """Test compiling hourly statistics."""
    zero = dt_util.utcnow()
    hass = hass_recorder()
    recorder = hass.data[DATA_INSTANCE]
    setup_component(hass, "sensor", {})
    attributes = {
        "device_class": device_class,
        "state_class": "measurement",
        "unit_of_measurement": unit,
    }
    four, states = record_states(hass, zero, "sensor.test1", attributes)
    hist = history.get_significant_states(hass, zero, four)
    assert dict(states) == dict(hist)

    recorder.do_adhoc_statistics(period="hourly", start=zero)
    wait_recording_done(hass)
    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {"statistic_id": "sensor.test1", "unit_of_measurement": native_unit}
    ]
    stats = statistics_during_period(hass, zero)
    assert stats == {
        "sensor.test1": [
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(zero),
                "mean": approx(mean),
                "min": approx(min),
                "max": approx(max),
                "last_reset": None,
                "state": None,
                "sum": None,
            }
        ]
    }
    assert "Error while processing event StatisticsTask" not in caplog.text


@pytest.mark.parametrize("attributes", [TEMPERATURE_SENSOR_ATTRIBUTES])
def test_compile_hourly_statistics_unsupported(hass_recorder, caplog, attributes):
    """Test compiling hourly statistics for unsupported sensor."""
    zero = dt_util.utcnow()
    hass = hass_recorder()
    recorder = hass.data[DATA_INSTANCE]
    setup_component(hass, "sensor", {})
    four, states = record_states(hass, zero, "sensor.test1", attributes)

    attributes_tmp = dict(attributes)
    attributes_tmp["unit_of_measurement"] = "invalid"
    _, _states = record_states(hass, zero, "sensor.test2", attributes_tmp)
    states = {**states, **_states}
    attributes_tmp.pop("unit_of_measurement")
    _, _states = record_states(hass, zero, "sensor.test3", attributes_tmp)
    states = {**states, **_states}

    attributes_tmp = dict(attributes)
    attributes_tmp["state_class"] = "invalid"
    _, _states = record_states(hass, zero, "sensor.test4", attributes_tmp)
    states = {**states, **_states}
    attributes_tmp.pop("state_class")
    _, _states = record_states(hass, zero, "sensor.test5", attributes_tmp)
    states = {**states, **_states}

    attributes_tmp = dict(attributes)
    attributes_tmp["device_class"] = "invalid"
    _, _states = record_states(hass, zero, "sensor.test6", attributes_tmp)
    states = {**states, **_states}
    attributes_tmp.pop("device_class")
    _, _states = record_states(hass, zero, "sensor.test7", attributes_tmp)
    states = {**states, **_states}

    hist = history.get_significant_states(hass, zero, four)
    assert dict(states) == dict(hist)

    recorder.do_adhoc_statistics(period="hourly", start=zero)
    wait_recording_done(hass)
    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {"statistic_id": "sensor.test1", "unit_of_measurement": "°C"},
        {"statistic_id": "sensor.test6", "unit_of_measurement": "°C"},
        {"statistic_id": "sensor.test7", "unit_of_measurement": "°C"},
    ]
    stats = statistics_during_period(hass, zero)
    assert stats == {
        "sensor.test1": [
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(zero),
                "mean": approx(16.440677966101696),
                "min": approx(10.0),
                "max": approx(30.0),
                "last_reset": None,
                "state": None,
                "sum": None,
            }
        ],
        "sensor.test6": [
            {
                "statistic_id": "sensor.test6",
                "start": process_timestamp_to_utc_isoformat(zero),
                "mean": approx(16.440677966101696),
                "min": approx(10.0),
                "max": approx(30.0),
                "last_reset": None,
                "state": None,
                "sum": None,
            }
        ],
        "sensor.test7": [
            {
                "statistic_id": "sensor.test7",
                "start": process_timestamp_to_utc_isoformat(zero),
                "mean": approx(16.440677966101696),
                "min": approx(10.0),
                "max": approx(30.0),
                "last_reset": None,
                "state": None,
                "sum": None,
            }
        ],
    }
    assert "Error while processing event StatisticsTask" not in caplog.text


@pytest.mark.parametrize("state_class", ["measurement", "total"])
@pytest.mark.parametrize(
    "device_class,unit,native_unit,factor",
    [
        ("energy", "kWh", "kWh", 1),
        ("energy", "Wh", "kWh", 1 / 1000),
        ("monetary", "EUR", "EUR", 1),
        ("monetary", "SEK", "SEK", 1),
        ("gas", "m³", "m³", 1),
        ("gas", "ft³", "m³", 0.0283168466),
    ],
)
def test_compile_hourly_sum_statistics_amount(
    hass_recorder, caplog, state_class, device_class, unit, native_unit, factor
):
    """Test compiling hourly statistics."""
    zero = dt_util.utcnow()
    hass = hass_recorder()
    recorder = hass.data[DATA_INSTANCE]
    setup_component(hass, "sensor", {})
    attributes = {
        "device_class": device_class,
        "state_class": state_class,
        "unit_of_measurement": unit,
        "last_reset": None,
    }
    seq = [10, 15, 20, 10, 30, 40, 50, 60, 70]

    four, eight, states = record_meter_states(
        hass, zero, "sensor.test1", attributes, seq
    )
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
    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {"statistic_id": "sensor.test1", "unit_of_measurement": native_unit}
    ]
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
                "state": approx(factor * seq[2]),
                "sum": approx(factor * 10.0),
            },
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(zero + timedelta(hours=1)),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": process_timestamp_to_utc_isoformat(four),
                "state": approx(factor * seq[5]),
                "sum": approx(factor * 40.0),
            },
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(zero + timedelta(hours=2)),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": process_timestamp_to_utc_isoformat(four),
                "state": approx(factor * seq[8]),
                "sum": approx(factor * 70.0),
            },
        ]
    }
    assert "Error while processing event StatisticsTask" not in caplog.text
    assert "Detected new cycle for sensor.test1, last_reset set to" in caplog.text
    assert "Compiling initial sum statistics for sensor.test1" in caplog.text
    assert "Detected new cycle for sensor.test1, value dropped" not in caplog.text


@pytest.mark.parametrize("state_class", ["measurement"])
@pytest.mark.parametrize(
    "device_class,unit,native_unit,factor",
    [
        ("energy", "kWh", "kWh", 1),
        ("energy", "Wh", "kWh", 1 / 1000),
        ("monetary", "EUR", "EUR", 1),
        ("monetary", "SEK", "SEK", 1),
        ("gas", "m³", "m³", 1),
        ("gas", "ft³", "m³", 0.0283168466),
    ],
)
def test_compile_hourly_sum_statistics_amount_reset_every_state_change(
    hass_recorder, caplog, state_class, device_class, unit, native_unit, factor
):
    """Test compiling hourly statistics."""
    zero = dt_util.utcnow()
    hass = hass_recorder()
    recorder = hass.data[DATA_INSTANCE]
    setup_component(hass, "sensor", {})
    attributes = {
        "device_class": device_class,
        "state_class": state_class,
        "unit_of_measurement": unit,
        "last_reset": None,
    }
    seq = [10, 15, 15, 15, 20, 20, 20, 10]
    # Make sure the sequence has consecutive equal states
    assert seq[1] == seq[2] == seq[3]

    states = {"sensor.test1": []}
    one = zero
    for i in range(len(seq)):
        one = one + timedelta(minutes=1)
        _states = record_meter_state(
            hass, one, "sensor.test1", attributes, seq[i : i + 1]
        )
        states["sensor.test1"].extend(_states["sensor.test1"])

    hist = history.get_significant_states(
        hass,
        zero - timedelta.resolution,
        one + timedelta.resolution,
        significant_changes_only=False,
    )
    assert dict(states)["sensor.test1"] == dict(hist)["sensor.test1"]

    recorder.do_adhoc_statistics(period="hourly", start=zero)
    wait_recording_done(hass)
    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {"statistic_id": "sensor.test1", "unit_of_measurement": native_unit}
    ]
    stats = statistics_during_period(hass, zero)
    assert stats == {
        "sensor.test1": [
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(zero),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": process_timestamp_to_utc_isoformat(one),
                "state": approx(factor * seq[7]),
                "sum": approx(factor * (sum(seq) - seq[0])),
            },
        ]
    }
    assert "Error while processing event StatisticsTask" not in caplog.text


@pytest.mark.parametrize(
    "device_class,unit,native_unit,factor",
    [
        ("energy", "kWh", "kWh", 1),
        ("energy", "Wh", "kWh", 1 / 1000),
        ("monetary", "EUR", "EUR", 1),
        ("monetary", "SEK", "SEK", 1),
        ("gas", "m³", "m³", 1),
        ("gas", "ft³", "m³", 0.0283168466),
    ],
)
def test_compile_hourly_sum_statistics_total_no_reset(
    hass_recorder, caplog, device_class, unit, native_unit, factor
):
    """Test compiling hourly statistics."""
    zero = dt_util.utcnow()
    hass = hass_recorder()
    recorder = hass.data[DATA_INSTANCE]
    setup_component(hass, "sensor", {})
    attributes = {
        "device_class": device_class,
        "state_class": "total",
        "unit_of_measurement": unit,
    }
    seq = [10, 15, 20, 10, 30, 40, 50, 60, 70]

    four, eight, states = record_meter_states(
        hass, zero, "sensor.test1", attributes, seq
    )
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
    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {"statistic_id": "sensor.test1", "unit_of_measurement": native_unit}
    ]
    stats = statistics_during_period(hass, zero)
    assert stats == {
        "sensor.test1": [
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(zero),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": None,
                "state": approx(factor * seq[2]),
                "sum": approx(factor * 10.0),
            },
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(zero + timedelta(hours=1)),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": None,
                "state": approx(factor * seq[5]),
                "sum": approx(factor * 30.0),
            },
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(zero + timedelta(hours=2)),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": None,
                "state": approx(factor * seq[8]),
                "sum": approx(factor * 60.0),
            },
        ]
    }
    assert "Error while processing event StatisticsTask" not in caplog.text


@pytest.mark.parametrize(
    "device_class,unit,native_unit,factor",
    [
        ("energy", "kWh", "kWh", 1),
        ("energy", "Wh", "kWh", 1 / 1000),
        ("gas", "m³", "m³", 1),
        ("gas", "ft³", "m³", 0.0283168466),
    ],
)
def test_compile_hourly_sum_statistics_total_increasing(
    hass_recorder, caplog, device_class, unit, native_unit, factor
):
    """Test compiling hourly statistics."""
    zero = dt_util.utcnow()
    hass = hass_recorder()
    recorder = hass.data[DATA_INSTANCE]
    setup_component(hass, "sensor", {})
    attributes = {
        "device_class": device_class,
        "state_class": "total_increasing",
        "unit_of_measurement": unit,
    }
    seq = [10, 15, 20, 10, 30, 40, 50, 60, 70]

    four, eight, states = record_meter_states(
        hass, zero, "sensor.test1", attributes, seq
    )
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
    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {"statistic_id": "sensor.test1", "unit_of_measurement": native_unit}
    ]
    stats = statistics_during_period(hass, zero)
    assert stats == {
        "sensor.test1": [
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(zero),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": None,
                "state": approx(factor * seq[2]),
                "sum": approx(factor * 10.0),
            },
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(zero + timedelta(hours=1)),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": None,
                "state": approx(factor * seq[5]),
                "sum": approx(factor * 50.0),
            },
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(zero + timedelta(hours=2)),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": None,
                "state": approx(factor * seq[8]),
                "sum": approx(factor * 80.0),
            },
        ]
    }
    assert "Error while processing event StatisticsTask" not in caplog.text
    assert "Detected new cycle for sensor.test1, last_reset set to" not in caplog.text
    assert "Compiling initial sum statistics for sensor.test1" in caplog.text
    assert "Detected new cycle for sensor.test1, value dropped" in caplog.text


@pytest.mark.parametrize(
    "device_class,unit,native_unit,factor",
    [("energy", "kWh", "kWh", 1)],
)
def test_compile_hourly_sum_statistics_total_increasing_small_dip(
    hass_recorder, caplog, device_class, unit, native_unit, factor
):
    """Test small dips in sensor readings do not trigger a reset."""
    zero = dt_util.utcnow()
    hass = hass_recorder()
    recorder = hass.data[DATA_INSTANCE]
    setup_component(hass, "sensor", {})
    attributes = {
        "device_class": device_class,
        "state_class": "total_increasing",
        "unit_of_measurement": unit,
    }
    seq = [10, 15, 20, 19, 30, 40, 39, 60, 70]

    four, eight, states = record_meter_states(
        hass, zero, "sensor.test1", attributes, seq
    )
    hist = history.get_significant_states(
        hass, zero - timedelta.resolution, eight + timedelta.resolution
    )
    assert dict(states)["sensor.test1"] == dict(hist)["sensor.test1"]

    recorder.do_adhoc_statistics(period="hourly", start=zero)
    wait_recording_done(hass)
    recorder.do_adhoc_statistics(period="hourly", start=zero + timedelta(hours=1))
    wait_recording_done(hass)
    assert (
        "Entity sensor.test1 has state class total_increasing, but its state is not "
        "strictly increasing. Please create a bug report at https://github.com/"
        "home-assistant/core/issues?q=is%3Aopen+is%3Aissue+label%3A%22integration%3A"
        "+recorder%22"
    ) not in caplog.text
    recorder.do_adhoc_statistics(period="hourly", start=zero + timedelta(hours=2))
    wait_recording_done(hass)
    assert (
        "Entity sensor.test1 has state class total_increasing, but its state is not "
        "strictly increasing. Please create a bug report at https://github.com/"
        "home-assistant/core/issues?q=is%3Aopen+is%3Aissue+label%3A%22integration%3A"
        "+recorder%22"
    ) in caplog.text
    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {"statistic_id": "sensor.test1", "unit_of_measurement": native_unit}
    ]
    stats = statistics_during_period(hass, zero)
    assert stats == {
        "sensor.test1": [
            {
                "last_reset": None,
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(zero),
                "max": None,
                "mean": None,
                "min": None,
                "state": approx(factor * seq[2]),
                "sum": approx(factor * 10.0),
            },
            {
                "last_reset": None,
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(zero + timedelta(hours=1)),
                "max": None,
                "mean": None,
                "min": None,
                "state": approx(factor * seq[5]),
                "sum": approx(factor * 30.0),
            },
            {
                "last_reset": None,
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(zero + timedelta(hours=2)),
                "max": None,
                "mean": None,
                "min": None,
                "state": approx(factor * seq[8]),
                "sum": approx(factor * 60.0),
            },
        ]
    }
    assert "Error while processing event StatisticsTask" not in caplog.text


def test_compile_hourly_energy_statistics_unsupported(hass_recorder, caplog):
    """Test compiling hourly statistics."""
    zero = dt_util.utcnow()
    hass = hass_recorder()
    recorder = hass.data[DATA_INSTANCE]
    setup_component(hass, "sensor", {})
    sns1_attr = {
        "device_class": "energy",
        "state_class": "measurement",
        "unit_of_measurement": "kWh",
        "last_reset": None,
    }
    sns2_attr = {"device_class": "energy"}
    sns3_attr = {}
    sns4_attr = {
        "device_class": "energy",
        "state_class": "measurement",
        "unit_of_measurement": "kWh",
    }
    seq1 = [10, 15, 20, 10, 30, 40, 50, 60, 70]
    seq2 = [110, 120, 130, 0, 30, 45, 55, 65, 75]
    seq3 = [0, 0, 5, 10, 30, 50, 60, 80, 90]
    seq4 = [0, 0, 5, 10, 30, 50, 60, 80, 90]

    four, eight, states = record_meter_states(
        hass, zero, "sensor.test1", sns1_attr, seq1
    )
    _, _, _states = record_meter_states(hass, zero, "sensor.test2", sns2_attr, seq2)
    states = {**states, **_states}
    _, _, _states = record_meter_states(hass, zero, "sensor.test3", sns3_attr, seq3)
    states = {**states, **_states}
    _, _, _states = record_meter_states(hass, zero, "sensor.test4", sns4_attr, seq4)
    states = {**states, **_states}

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
    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {"statistic_id": "sensor.test1", "unit_of_measurement": "kWh"}
    ]
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
                "state": approx(20.0),
                "sum": approx(10.0),
            },
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(zero + timedelta(hours=1)),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": process_timestamp_to_utc_isoformat(four),
                "state": approx(40.0),
                "sum": approx(40.0),
            },
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(zero + timedelta(hours=2)),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": process_timestamp_to_utc_isoformat(four),
                "state": approx(70.0),
                "sum": approx(70.0),
            },
        ]
    }
    assert "Error while processing event StatisticsTask" not in caplog.text


def test_compile_hourly_energy_statistics_multiple(hass_recorder, caplog):
    """Test compiling multiple hourly statistics."""
    zero = dt_util.utcnow()
    hass = hass_recorder()
    recorder = hass.data[DATA_INSTANCE]
    setup_component(hass, "sensor", {})
    sns1_attr = {**ENERGY_SENSOR_ATTRIBUTES, "last_reset": None}
    sns2_attr = {**ENERGY_SENSOR_ATTRIBUTES, "last_reset": None}
    sns3_attr = {
        **ENERGY_SENSOR_ATTRIBUTES,
        "unit_of_measurement": "Wh",
        "last_reset": None,
    }
    sns4_attr = {**ENERGY_SENSOR_ATTRIBUTES}
    seq1 = [10, 15, 20, 10, 30, 40, 50, 60, 70]
    seq2 = [110, 120, 130, 0, 30, 45, 55, 65, 75]
    seq3 = [0, 0, 5, 10, 30, 50, 60, 80, 90]
    seq4 = [0, 0, 5, 10, 30, 50, 60, 80, 90]

    four, eight, states = record_meter_states(
        hass, zero, "sensor.test1", sns1_attr, seq1
    )
    _, _, _states = record_meter_states(hass, zero, "sensor.test2", sns2_attr, seq2)
    states = {**states, **_states}
    _, _, _states = record_meter_states(hass, zero, "sensor.test3", sns3_attr, seq3)
    states = {**states, **_states}
    _, _, _states = record_meter_states(hass, zero, "sensor.test4", sns4_attr, seq4)
    states = {**states, **_states}
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
    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {"statistic_id": "sensor.test1", "unit_of_measurement": "kWh"},
        {"statistic_id": "sensor.test2", "unit_of_measurement": "kWh"},
        {"statistic_id": "sensor.test3", "unit_of_measurement": "kWh"},
    ]
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
                "state": approx(20.0),
                "sum": approx(10.0),
            },
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(zero + timedelta(hours=1)),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": process_timestamp_to_utc_isoformat(four),
                "state": approx(40.0),
                "sum": approx(40.0),
            },
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(zero + timedelta(hours=2)),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": process_timestamp_to_utc_isoformat(four),
                "state": approx(70.0),
                "sum": approx(70.0),
            },
        ],
        "sensor.test2": [
            {
                "statistic_id": "sensor.test2",
                "start": process_timestamp_to_utc_isoformat(zero),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": process_timestamp_to_utc_isoformat(zero),
                "state": approx(130.0),
                "sum": approx(20.0),
            },
            {
                "statistic_id": "sensor.test2",
                "start": process_timestamp_to_utc_isoformat(zero + timedelta(hours=1)),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": process_timestamp_to_utc_isoformat(four),
                "state": approx(45.0),
                "sum": approx(-65.0),
            },
            {
                "statistic_id": "sensor.test2",
                "start": process_timestamp_to_utc_isoformat(zero + timedelta(hours=2)),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": process_timestamp_to_utc_isoformat(four),
                "state": approx(75.0),
                "sum": approx(-35.0),
            },
        ],
        "sensor.test3": [
            {
                "statistic_id": "sensor.test3",
                "start": process_timestamp_to_utc_isoformat(zero),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": process_timestamp_to_utc_isoformat(zero),
                "state": approx(5.0 / 1000),
                "sum": approx(5.0 / 1000),
            },
            {
                "statistic_id": "sensor.test3",
                "start": process_timestamp_to_utc_isoformat(zero + timedelta(hours=1)),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": process_timestamp_to_utc_isoformat(four),
                "state": approx(50.0 / 1000),
                "sum": approx(60.0 / 1000),
            },
            {
                "statistic_id": "sensor.test3",
                "start": process_timestamp_to_utc_isoformat(zero + timedelta(hours=2)),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": process_timestamp_to_utc_isoformat(four),
                "state": approx(90.0 / 1000),
                "sum": approx(100.0 / 1000),
            },
        ],
    }
    assert "Error while processing event StatisticsTask" not in caplog.text


@pytest.mark.parametrize(
    "device_class,unit,value",
    [
        ("battery", "%", 30),
        ("battery", None, 30),
        ("humidity", "%", 30),
        ("humidity", None, 30),
        ("pressure", "Pa", 30),
        ("pressure", "hPa", 3000),
        ("pressure", "mbar", 3000),
        ("pressure", "inHg", 101591.67),
        ("pressure", "psi", 206842.71),
        ("temperature", "°C", 30),
        ("temperature", "°F", -1.111111),
    ],
)
def test_compile_hourly_statistics_unchanged(
    hass_recorder, caplog, device_class, unit, value
):
    """Test compiling hourly statistics, with no changes during the hour."""
    zero = dt_util.utcnow()
    hass = hass_recorder()
    recorder = hass.data[DATA_INSTANCE]
    setup_component(hass, "sensor", {})
    attributes = {
        "device_class": device_class,
        "state_class": "measurement",
        "unit_of_measurement": unit,
    }
    four, states = record_states(hass, zero, "sensor.test1", attributes)
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
                "mean": approx(value),
                "min": approx(value),
                "max": approx(value),
                "last_reset": None,
                "state": None,
                "sum": None,
            }
        ]
    }
    assert "Error while processing event StatisticsTask" not in caplog.text


def test_compile_hourly_statistics_partially_unavailable(hass_recorder, caplog):
    """Test compiling hourly statistics, with the sensor being partially unavailable."""
    zero = dt_util.utcnow()
    hass = hass_recorder()
    recorder = hass.data[DATA_INSTANCE]
    setup_component(hass, "sensor", {})
    four, states = record_states_partially_unavailable(
        hass, zero, "sensor.test1", TEMPERATURE_SENSOR_ATTRIBUTES
    )
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
                "mean": approx(21.1864406779661),
                "min": approx(10.0),
                "max": approx(25.0),
                "last_reset": None,
                "state": None,
                "sum": None,
            }
        ]
    }
    assert "Error while processing event StatisticsTask" not in caplog.text


@pytest.mark.parametrize(
    "device_class,unit,value",
    [
        ("battery", "%", 30),
        ("battery", None, 30),
        ("humidity", "%", 30),
        ("humidity", None, 30),
        ("pressure", "Pa", 30),
        ("pressure", "hPa", 3000),
        ("pressure", "mbar", 3000),
        ("pressure", "inHg", 101591.67),
        ("pressure", "psi", 206842.71),
        ("temperature", "°C", 30),
        ("temperature", "°F", -1.111111),
    ],
)
def test_compile_hourly_statistics_unavailable(
    hass_recorder, caplog, device_class, unit, value
):
    """Test compiling hourly statistics, with the sensor being unavailable."""
    zero = dt_util.utcnow()
    hass = hass_recorder()
    recorder = hass.data[DATA_INSTANCE]
    setup_component(hass, "sensor", {})
    attributes = {
        "device_class": device_class,
        "state_class": "measurement",
        "unit_of_measurement": unit,
    }
    four, states = record_states_partially_unavailable(
        hass, zero, "sensor.test1", attributes
    )
    _, _states = record_states(hass, zero, "sensor.test2", attributes)
    states = {**states, **_states}
    hist = history.get_significant_states(hass, zero, four)
    assert dict(states) == dict(hist)

    recorder.do_adhoc_statistics(period="hourly", start=four)
    wait_recording_done(hass)
    stats = statistics_during_period(hass, four)
    assert stats == {
        "sensor.test2": [
            {
                "statistic_id": "sensor.test2",
                "start": process_timestamp_to_utc_isoformat(four),
                "mean": approx(value),
                "min": approx(value),
                "max": approx(value),
                "last_reset": None,
                "state": None,
                "sum": None,
            }
        ]
    }
    assert "Error while processing event StatisticsTask" not in caplog.text


def test_compile_hourly_statistics_fails(hass_recorder, caplog):
    """Test compiling hourly statistics throws."""
    zero = dt_util.utcnow()
    hass = hass_recorder()
    recorder = hass.data[DATA_INSTANCE]
    setup_component(hass, "sensor", {})
    with patch(
        "homeassistant.components.sensor.recorder.compile_statistics",
        side_effect=Exception,
    ):
        recorder.do_adhoc_statistics(period="hourly", start=zero)
        wait_recording_done(hass)
    assert "Error while processing event StatisticsTask" in caplog.text


@pytest.mark.parametrize(
    "device_class,unit,native_unit,statistic_type",
    [
        ("battery", "%", "%", "mean"),
        ("battery", None, None, "mean"),
        ("energy", "Wh", "kWh", "sum"),
        ("energy", "kWh", "kWh", "sum"),
        ("humidity", "%", "%", "mean"),
        ("humidity", None, None, "mean"),
        ("monetary", "USD", "USD", "sum"),
        ("monetary", "None", "None", "sum"),
        ("gas", "m³", "m³", "sum"),
        ("gas", "ft³", "m³", "sum"),
        ("pressure", "Pa", "Pa", "mean"),
        ("pressure", "hPa", "Pa", "mean"),
        ("pressure", "mbar", "Pa", "mean"),
        ("pressure", "inHg", "Pa", "mean"),
        ("pressure", "psi", "Pa", "mean"),
        ("temperature", "°C", "°C", "mean"),
        ("temperature", "°F", "°C", "mean"),
    ],
)
def test_list_statistic_ids(
    hass_recorder, caplog, device_class, unit, native_unit, statistic_type
):
    """Test listing future statistic ids."""
    hass = hass_recorder()
    setup_component(hass, "sensor", {})
    attributes = {
        "device_class": device_class,
        "last_reset": 0,
        "state_class": "measurement",
        "unit_of_measurement": unit,
    }
    hass.states.set("sensor.test1", 0, attributes=attributes)
    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {"statistic_id": "sensor.test1", "unit_of_measurement": native_unit}
    ]
    for stat_type in ["mean", "sum", "dogs"]:
        statistic_ids = list_statistic_ids(hass, statistic_type=stat_type)
        if statistic_type == stat_type:
            assert statistic_ids == [
                {"statistic_id": "sensor.test1", "unit_of_measurement": native_unit}
            ]
        else:
            assert statistic_ids == []


@pytest.mark.parametrize(
    "_attributes",
    [{**ENERGY_SENSOR_ATTRIBUTES, "last_reset": 0}, TEMPERATURE_SENSOR_ATTRIBUTES],
)
def test_list_statistic_ids_unsupported(hass_recorder, caplog, _attributes):
    """Test listing future statistic ids for unsupported sensor."""
    hass = hass_recorder()
    setup_component(hass, "sensor", {})
    attributes = dict(_attributes)
    hass.states.set("sensor.test1", 0, attributes=attributes)
    if "last_reset" in attributes:
        attributes.pop("unit_of_measurement")
        hass.states.set("last_reset.test2", 0, attributes=attributes)
    attributes = dict(_attributes)
    if "unit_of_measurement" in attributes:
        attributes["unit_of_measurement"] = "invalid"
        hass.states.set("sensor.test3", 0, attributes=attributes)
        attributes.pop("unit_of_measurement")
        hass.states.set("sensor.test4", 0, attributes=attributes)
    attributes = dict(_attributes)
    attributes["state_class"] = "invalid"
    hass.states.set("sensor.test5", 0, attributes=attributes)
    attributes.pop("state_class")
    hass.states.set("sensor.test6", 0, attributes=attributes)


@pytest.mark.parametrize(
    "device_class,unit,native_unit,mean,min,max",
    [
        (None, None, None, 16.440677, 10, 30),
        (None, "%", "%", 16.440677, 10, 30),
        ("battery", "%", "%", 16.440677, 10, 30),
        ("battery", None, None, 16.440677, 10, 30),
    ],
)
def test_compile_hourly_statistics_changing_units_1(
    hass_recorder, caplog, device_class, unit, native_unit, mean, min, max
):
    """Test compiling hourly statistics where units change from one hour to the next."""
    zero = dt_util.utcnow()
    hass = hass_recorder()
    recorder = hass.data[DATA_INSTANCE]
    setup_component(hass, "sensor", {})
    attributes = {
        "device_class": device_class,
        "state_class": "measurement",
        "unit_of_measurement": unit,
    }
    four, states = record_states(hass, zero, "sensor.test1", attributes)
    attributes["unit_of_measurement"] = "cats"
    four, _states = record_states(
        hass, zero + timedelta(hours=1), "sensor.test1", attributes
    )
    states["sensor.test1"] += _states["sensor.test1"]
    four, _states = record_states(
        hass, zero + timedelta(hours=2), "sensor.test1", attributes
    )
    states["sensor.test1"] += _states["sensor.test1"]
    hist = history.get_significant_states(hass, zero, four)
    assert dict(states) == dict(hist)

    recorder.do_adhoc_statistics(period="hourly", start=zero)
    wait_recording_done(hass)
    assert "does not match the unit of already compiled" not in caplog.text
    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {"statistic_id": "sensor.test1", "unit_of_measurement": native_unit}
    ]
    stats = statistics_during_period(hass, zero)
    assert stats == {
        "sensor.test1": [
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(zero),
                "mean": approx(mean),
                "min": approx(min),
                "max": approx(max),
                "last_reset": None,
                "state": None,
                "sum": None,
            }
        ]
    }

    recorder.do_adhoc_statistics(period="hourly", start=zero + timedelta(hours=2))
    wait_recording_done(hass)
    assert (
        "The unit of sensor.test1 (cats) does not match the unit of already compiled "
        f"statistics ({native_unit})" in caplog.text
    )
    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {"statistic_id": "sensor.test1", "unit_of_measurement": native_unit}
    ]
    stats = statistics_during_period(hass, zero)
    assert stats == {
        "sensor.test1": [
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(zero),
                "mean": approx(mean),
                "min": approx(min),
                "max": approx(max),
                "last_reset": None,
                "state": None,
                "sum": None,
            }
        ]
    }
    assert "Error while processing event StatisticsTask" not in caplog.text


@pytest.mark.parametrize(
    "device_class,unit,native_unit,mean,min,max",
    [
        (None, None, None, 16.440677, 10, 30),
        (None, "%", "%", 16.440677, 10, 30),
        ("battery", "%", "%", 16.440677, 10, 30),
        ("battery", None, None, 16.440677, 10, 30),
    ],
)
def test_compile_hourly_statistics_changing_units_2(
    hass_recorder, caplog, device_class, unit, native_unit, mean, min, max
):
    """Test compiling hourly statistics where units change during an hour."""
    zero = dt_util.utcnow()
    hass = hass_recorder()
    recorder = hass.data[DATA_INSTANCE]
    setup_component(hass, "sensor", {})
    attributes = {
        "device_class": device_class,
        "state_class": "measurement",
        "unit_of_measurement": unit,
    }
    four, states = record_states(hass, zero, "sensor.test1", attributes)
    attributes["unit_of_measurement"] = "cats"
    four, _states = record_states(
        hass, zero + timedelta(hours=1), "sensor.test1", attributes
    )
    states["sensor.test1"] += _states["sensor.test1"]
    hist = history.get_significant_states(hass, zero, four)
    assert dict(states) == dict(hist)

    recorder.do_adhoc_statistics(period="hourly", start=zero + timedelta(minutes=30))
    wait_recording_done(hass)
    assert "The unit of sensor.test1 is changing" in caplog.text
    assert "and matches the unit of already compiled statistics" not in caplog.text
    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {"statistic_id": "sensor.test1", "unit_of_measurement": "cats"}
    ]
    stats = statistics_during_period(hass, zero)
    assert stats == {}

    assert "Error while processing event StatisticsTask" not in caplog.text


@pytest.mark.parametrize(
    "device_class,unit,native_unit,mean,min,max",
    [
        (None, None, None, 16.440677, 10, 30),
        (None, "%", "%", 16.440677, 10, 30),
        ("battery", "%", "%", 16.440677, 10, 30),
        ("battery", None, None, 16.440677, 10, 30),
    ],
)
def test_compile_hourly_statistics_changing_units_3(
    hass_recorder, caplog, device_class, unit, native_unit, mean, min, max
):
    """Test compiling hourly statistics where units change from one hour to the next."""
    zero = dt_util.utcnow()
    hass = hass_recorder()
    recorder = hass.data[DATA_INSTANCE]
    setup_component(hass, "sensor", {})
    attributes = {
        "device_class": device_class,
        "state_class": "measurement",
        "unit_of_measurement": unit,
    }
    four, states = record_states(hass, zero, "sensor.test1", attributes)
    four, _states = record_states(
        hass, zero + timedelta(hours=1), "sensor.test1", attributes
    )
    states["sensor.test1"] += _states["sensor.test1"]
    attributes["unit_of_measurement"] = "cats"
    four, _states = record_states(
        hass, zero + timedelta(hours=2), "sensor.test1", attributes
    )
    states["sensor.test1"] += _states["sensor.test1"]
    hist = history.get_significant_states(hass, zero, four)
    assert dict(states) == dict(hist)

    recorder.do_adhoc_statistics(period="hourly", start=zero)
    wait_recording_done(hass)
    assert "does not match the unit of already compiled" not in caplog.text
    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {"statistic_id": "sensor.test1", "unit_of_measurement": native_unit}
    ]
    stats = statistics_during_period(hass, zero)
    assert stats == {
        "sensor.test1": [
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(zero),
                "mean": approx(mean),
                "min": approx(min),
                "max": approx(max),
                "last_reset": None,
                "state": None,
                "sum": None,
            }
        ]
    }

    recorder.do_adhoc_statistics(period="hourly", start=zero + timedelta(hours=2))
    wait_recording_done(hass)
    assert "The unit of sensor.test1 is changing" in caplog.text
    assert f"matches the unit of already compiled statistics ({unit})" in caplog.text
    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {"statistic_id": "sensor.test1", "unit_of_measurement": native_unit}
    ]
    stats = statistics_during_period(hass, zero)
    assert stats == {
        "sensor.test1": [
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(zero),
                "mean": approx(mean),
                "min": approx(min),
                "max": approx(max),
                "last_reset": None,
                "state": None,
                "sum": None,
            }
        ]
    }
    assert "Error while processing event StatisticsTask" not in caplog.text


@pytest.mark.parametrize(
    "device_class,unit,native_unit,mean,min,max",
    [
        (None, None, None, 16.440677, 10, 30),
    ],
)
def test_compile_hourly_statistics_changing_statistics(
    hass_recorder, caplog, device_class, unit, native_unit, mean, min, max
):
    """Test compiling hourly statistics where units change during an hour."""
    zero = dt_util.utcnow()
    hass = hass_recorder()
    recorder = hass.data[DATA_INSTANCE]
    setup_component(hass, "sensor", {})
    attributes_1 = {
        "device_class": device_class,
        "state_class": "measurement",
        "unit_of_measurement": unit,
    }
    attributes_2 = {
        "device_class": device_class,
        "state_class": "total_increasing",
        "unit_of_measurement": unit,
    }
    four, states = record_states(hass, zero, "sensor.test1", attributes_1)
    recorder.do_adhoc_statistics(period="hourly", start=zero)
    wait_recording_done(hass)
    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {"statistic_id": "sensor.test1", "unit_of_measurement": None}
    ]
    metadata = get_metadata(hass, "sensor.test1")
    assert metadata == {
        "has_mean": True,
        "has_sum": False,
        "statistic_id": "sensor.test1",
        "unit_of_measurement": None,
    }

    # Add more states, with changed state class
    four, _states = record_states(
        hass, zero + timedelta(hours=1), "sensor.test1", attributes_2
    )
    states["sensor.test1"] += _states["sensor.test1"]
    hist = history.get_significant_states(hass, zero, four)
    assert dict(states) == dict(hist)

    recorder.do_adhoc_statistics(period="hourly", start=zero + timedelta(hours=1))
    wait_recording_done(hass)
    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {"statistic_id": "sensor.test1", "unit_of_measurement": None}
    ]
    metadata = get_metadata(hass, "sensor.test1")
    assert metadata == {
        "has_mean": False,
        "has_sum": True,
        "statistic_id": "sensor.test1",
        "unit_of_measurement": None,
    }
    stats = statistics_during_period(hass, zero)
    assert stats == {
        "sensor.test1": [
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(zero),
                "mean": approx(mean),
                "min": approx(min),
                "max": approx(max),
                "last_reset": None,
                "state": None,
                "sum": None,
            },
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(zero + timedelta(hours=1)),
                "mean": None,
                "min": None,
                "max": None,
                "last_reset": None,
                "state": approx(30.0),
                "sum": approx(30.0),
            },
        ]
    }

    assert "Error while processing event StatisticsTask" not in caplog.text


def record_states(hass, zero, entity_id, attributes):
    """Record some test states.

    We inject a bunch of state updates for measurement sensors.
    """
    attributes = dict(attributes)

    def set_state(entity_id, state, **kwargs):
        """Set the state."""
        hass.states.set(entity_id, state, **kwargs)
        wait_recording_done(hass)
        return hass.states.get(entity_id)

    one = zero + timedelta(minutes=1)
    two = one + timedelta(minutes=10)
    three = two + timedelta(minutes=40)
    four = three + timedelta(minutes=10)

    states = {entity_id: []}
    with patch("homeassistant.components.recorder.dt_util.utcnow", return_value=one):
        states[entity_id].append(set_state(entity_id, "10", attributes=attributes))

    with patch("homeassistant.components.recorder.dt_util.utcnow", return_value=two):
        states[entity_id].append(set_state(entity_id, "15", attributes=attributes))

    with patch("homeassistant.components.recorder.dt_util.utcnow", return_value=three):
        states[entity_id].append(set_state(entity_id, "30", attributes=attributes))

    return four, states


def record_meter_states(hass, zero, entity_id, _attributes, seq):
    """Record some test states.

    We inject a bunch of state updates for meter sensors.
    """

    def set_state(entity_id, state, **kwargs):
        """Set the state."""
        hass.states.set(entity_id, state, **kwargs)
        wait_recording_done(hass)
        return hass.states.get(entity_id)

    one = zero + timedelta(minutes=15)
    two = one + timedelta(minutes=30)
    three = two + timedelta(minutes=15)
    four = three + timedelta(minutes=15)
    five = four + timedelta(minutes=30)
    six = five + timedelta(minutes=15)
    seven = six + timedelta(minutes=15)
    eight = seven + timedelta(minutes=30)

    attributes = dict(_attributes)
    if "last_reset" in _attributes:
        attributes["last_reset"] = zero.isoformat()

    states = {entity_id: []}
    with patch("homeassistant.components.recorder.dt_util.utcnow", return_value=zero):
        states[entity_id].append(set_state(entity_id, seq[0], attributes=attributes))

    with patch("homeassistant.components.recorder.dt_util.utcnow", return_value=one):
        states[entity_id].append(set_state(entity_id, seq[1], attributes=attributes))

    with patch("homeassistant.components.recorder.dt_util.utcnow", return_value=two):
        states[entity_id].append(set_state(entity_id, seq[2], attributes=attributes))

    with patch("homeassistant.components.recorder.dt_util.utcnow", return_value=three):
        states[entity_id].append(set_state(entity_id, seq[3], attributes=attributes))

    attributes = dict(_attributes)
    if "last_reset" in _attributes:
        attributes["last_reset"] = four.isoformat()

    with patch("homeassistant.components.recorder.dt_util.utcnow", return_value=four):
        states[entity_id].append(set_state(entity_id, seq[4], attributes=attributes))

    with patch("homeassistant.components.recorder.dt_util.utcnow", return_value=five):
        states[entity_id].append(set_state(entity_id, seq[5], attributes=attributes))

    with patch("homeassistant.components.recorder.dt_util.utcnow", return_value=six):
        states[entity_id].append(set_state(entity_id, seq[6], attributes=attributes))

    with patch("homeassistant.components.recorder.dt_util.utcnow", return_value=seven):
        states[entity_id].append(set_state(entity_id, seq[7], attributes=attributes))

    with patch("homeassistant.components.recorder.dt_util.utcnow", return_value=eight):
        states[entity_id].append(set_state(entity_id, seq[8], attributes=attributes))

    return four, eight, states


def record_meter_state(hass, zero, entity_id, _attributes, seq):
    """Record test state.

    We inject a state update for meter sensor.
    """

    def set_state(entity_id, state, **kwargs):
        """Set the state."""
        hass.states.set(entity_id, state, **kwargs)
        wait_recording_done(hass)
        return hass.states.get(entity_id)

    attributes = dict(_attributes)
    attributes["last_reset"] = zero.isoformat()

    states = {entity_id: []}
    with patch("homeassistant.components.recorder.dt_util.utcnow", return_value=zero):
        states[entity_id].append(set_state(entity_id, seq[0], attributes=attributes))

    return states


def record_states_partially_unavailable(hass, zero, entity_id, attributes):
    """Record some test states.

    We inject a bunch of state updates temperature sensors.
    """

    def set_state(entity_id, state, **kwargs):
        """Set the state."""
        hass.states.set(entity_id, state, **kwargs)
        wait_recording_done(hass)
        return hass.states.get(entity_id)

    one = zero + timedelta(minutes=1)
    two = one + timedelta(minutes=15)
    three = two + timedelta(minutes=30)
    four = three + timedelta(minutes=15)

    states = {entity_id: []}
    with patch("homeassistant.components.recorder.dt_util.utcnow", return_value=one):
        states[entity_id].append(set_state(entity_id, "10", attributes=attributes))

    with patch("homeassistant.components.recorder.dt_util.utcnow", return_value=two):
        states[entity_id].append(set_state(entity_id, "25", attributes=attributes))

    with patch("homeassistant.components.recorder.dt_util.utcnow", return_value=three):
        states[entity_id].append(
            set_state(entity_id, STATE_UNAVAILABLE, attributes=attributes)
        )

    return four, states
