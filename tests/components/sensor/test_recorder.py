"""The tests for sensor recorder platform."""
# pylint: disable=protected-access,invalid-name
from datetime import timedelta
import math
from statistics import mean
from unittest.mock import patch

import pytest
from pytest import approx

from homeassistant import loader
from homeassistant.components.recorder import history
from homeassistant.components.recorder.db_schema import StatisticsMeta
from homeassistant.components.recorder.models import process_timestamp_to_utc_isoformat
from homeassistant.components.recorder.statistics import (
    get_metadata,
    list_statistic_ids,
    statistics_during_period,
)
from homeassistant.components.recorder.util import get_instance, session_scope
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.setup import async_setup_component, setup_component
import homeassistant.util.dt as dt_util
from homeassistant.util.unit_system import IMPERIAL_SYSTEM, METRIC_SYSTEM

from tests.components.recorder.common import (
    async_recorder_block_till_done,
    async_wait_recording_done,
    do_adhoc_statistics,
    wait_recording_done,
)

BATTERY_SENSOR_ATTRIBUTES = {
    "device_class": "battery",
    "state_class": "measurement",
    "unit_of_measurement": "%",
}
ENERGY_SENSOR_ATTRIBUTES = {
    "device_class": "energy",
    "state_class": "total",
    "unit_of_measurement": "kWh",
}
NONE_SENSOR_ATTRIBUTES = {
    "state_class": "measurement",
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
    "state_class": "total",
    "unit_of_measurement": "m³",
}


@pytest.fixture(autouse=True)
def set_time_zone():
    """Set the time zone for the tests."""
    # Set our timezone to CST/Regina so we can check calculations
    # This keeps UTC-6 all year round
    dt_util.set_default_time_zone(dt_util.get_time_zone("America/Regina"))
    yield
    dt_util.set_default_time_zone(dt_util.get_time_zone("UTC"))


@pytest.mark.parametrize(
    "device_class,state_unit,display_unit,statistics_unit,mean,min,max",
    [
        (None, "%", "%", "%", 13.050847, -10, 30),
        ("battery", "%", "%", "%", 13.050847, -10, 30),
        ("battery", None, None, None, 13.050847, -10, 30),
        ("humidity", "%", "%", "%", 13.050847, -10, 30),
        ("humidity", None, None, None, 13.050847, -10, 30),
        ("pressure", "Pa", "Pa", "Pa", 13.050847, -10, 30),
        ("pressure", "hPa", "Pa", "Pa", 1305.0847, -1000, 3000),
        ("pressure", "mbar", "Pa", "Pa", 1305.0847, -1000, 3000),
        ("pressure", "inHg", "Pa", "Pa", 44195.25, -33863.89, 101591.67),
        ("pressure", "psi", "Pa", "Pa", 89982.42, -68947.57, 206842.71),
        ("temperature", "°C", "°C", "°C", 13.050847, -10, 30),
        ("temperature", "°F", "°C", "°C", -10.52731, -23.33333, -1.111111),
    ],
)
def test_compile_hourly_statistics(
    hass_recorder,
    caplog,
    device_class,
    state_unit,
    display_unit,
    statistics_unit,
    mean,
    min,
    max,
):
    """Test compiling hourly statistics."""
    zero = dt_util.utcnow()
    hass = hass_recorder()
    setup_component(hass, "sensor", {})
    wait_recording_done(hass)  # Wait for the sensor recorder platform to be added
    attributes = {
        "device_class": device_class,
        "state_class": "measurement",
        "unit_of_measurement": state_unit,
    }
    four, states = record_states(hass, zero, "sensor.test1", attributes)
    hist = history.get_significant_states(hass, zero, four)
    assert dict(states) == dict(hist)

    do_adhoc_statistics(hass, start=zero)
    wait_recording_done(hass)
    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {
            "statistic_id": "sensor.test1",
            "display_unit_of_measurement": display_unit,
            "has_mean": True,
            "has_sum": False,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": statistics_unit,
        }
    ]
    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {
        "sensor.test1": [
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(zero),
                "end": process_timestamp_to_utc_isoformat(zero + timedelta(minutes=5)),
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
    "device_class,state_unit,display_unit,statistics_unit",
    [
        (None, "%", "%", "%"),
    ],
)
def test_compile_hourly_statistics_purged_state_changes(
    hass_recorder, caplog, device_class, state_unit, display_unit, statistics_unit
):
    """Test compiling hourly statistics."""
    zero = dt_util.utcnow()
    hass = hass_recorder()
    setup_component(hass, "sensor", {})
    wait_recording_done(hass)  # Wait for the sensor recorder platform to be added
    attributes = {
        "device_class": device_class,
        "state_class": "measurement",
        "unit_of_measurement": state_unit,
    }
    four, states = record_states(hass, zero, "sensor.test1", attributes)
    hist = history.get_significant_states(hass, zero, four)
    assert dict(states) == dict(hist)

    mean = min = max = float(hist["sensor.test1"][-1].state)

    # Purge all states from the database
    with patch(
        "homeassistant.components.recorder.core.dt_util.utcnow", return_value=four
    ):
        hass.services.call("recorder", "purge", {"keep_days": 0})
        hass.block_till_done()
        wait_recording_done(hass)
    hist = history.get_significant_states(hass, zero, four)
    assert not hist

    do_adhoc_statistics(hass, start=zero)
    wait_recording_done(hass)
    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {
            "display_unit_of_measurement": display_unit,
            "statistic_id": "sensor.test1",
            "has_mean": True,
            "has_sum": False,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": statistics_unit,
        }
    ]
    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {
        "sensor.test1": [
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(zero),
                "end": process_timestamp_to_utc_isoformat(zero + timedelta(minutes=5)),
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
    setup_component(hass, "sensor", {})
    wait_recording_done(hass)  # Wait for the sensor recorder platform to be added
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

    do_adhoc_statistics(hass, start=zero)
    wait_recording_done(hass)
    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {
            "statistic_id": "sensor.test1",
            "display_unit_of_measurement": "°C",
            "has_mean": True,
            "has_sum": False,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": "°C",
        },
        {
            "statistic_id": "sensor.test6",
            "display_unit_of_measurement": "°C",
            "has_mean": True,
            "has_sum": False,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": "°C",
        },
        {
            "statistic_id": "sensor.test7",
            "display_unit_of_measurement": "°C",
            "has_mean": True,
            "has_sum": False,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": "°C",
        },
    ]
    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {
        "sensor.test1": [
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(zero),
                "end": process_timestamp_to_utc_isoformat(zero + timedelta(minutes=5)),
                "mean": approx(13.050847),
                "min": approx(-10.0),
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
                "end": process_timestamp_to_utc_isoformat(zero + timedelta(minutes=5)),
                "mean": approx(13.050847),
                "min": approx(-10.0),
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
                "end": process_timestamp_to_utc_isoformat(zero + timedelta(minutes=5)),
                "mean": approx(13.050847),
                "min": approx(-10.0),
                "max": approx(30.0),
                "last_reset": None,
                "state": None,
                "sum": None,
            }
        ],
    }
    assert "Error while processing event StatisticsTask" not in caplog.text


@pytest.mark.parametrize("state_class", ["total"])
@pytest.mark.parametrize(
    "units,device_class,state_unit,display_unit,statistics_unit,factor",
    [
        (IMPERIAL_SYSTEM, "energy", "kWh", "kWh", "kWh", 1),
        (IMPERIAL_SYSTEM, "energy", "Wh", "kWh", "kWh", 1 / 1000),
        (IMPERIAL_SYSTEM, "monetary", "EUR", "EUR", "EUR", 1),
        (IMPERIAL_SYSTEM, "monetary", "SEK", "SEK", "SEK", 1),
        (IMPERIAL_SYSTEM, "gas", "m³", "ft³", "m³", 35.314666711),
        (IMPERIAL_SYSTEM, "gas", "ft³", "ft³", "m³", 1),
        (METRIC_SYSTEM, "energy", "kWh", "kWh", "kWh", 1),
        (METRIC_SYSTEM, "energy", "Wh", "kWh", "kWh", 1 / 1000),
        (METRIC_SYSTEM, "monetary", "EUR", "EUR", "EUR", 1),
        (METRIC_SYSTEM, "monetary", "SEK", "SEK", "SEK", 1),
        (METRIC_SYSTEM, "gas", "m³", "m³", "m³", 1),
        (METRIC_SYSTEM, "gas", "ft³", "m³", "m³", 0.0283168466),
    ],
)
async def test_compile_hourly_sum_statistics_amount(
    hass,
    hass_ws_client,
    recorder_mock,
    caplog,
    units,
    state_class,
    device_class,
    state_unit,
    display_unit,
    statistics_unit,
    factor,
):
    """Test compiling hourly statistics."""
    period0 = dt_util.utcnow()
    period0_end = period1 = period0 + timedelta(minutes=5)
    period1_end = period2 = period0 + timedelta(minutes=10)
    period2_end = period0 + timedelta(minutes=15)
    client = await hass_ws_client()
    hass.config.units = units
    await async_setup_component(hass, "sensor", {})
    # Wait for the sensor recorder platform to be added
    await async_recorder_block_till_done(hass)
    attributes = {
        "device_class": device_class,
        "state_class": state_class,
        "unit_of_measurement": state_unit,
        "last_reset": None,
    }
    seq = [10, 15, 20, 10, 30, 40, 50, 60, 70]

    four, eight, states = await hass.async_add_executor_job(
        record_meter_states, hass, period0, "sensor.test1", attributes, seq
    )
    await async_wait_recording_done(hass)
    hist = history.get_significant_states(
        hass, period0 - timedelta.resolution, eight + timedelta.resolution
    )
    assert dict(states)["sensor.test1"] == dict(hist)["sensor.test1"]

    do_adhoc_statistics(hass, start=period0)
    await async_wait_recording_done(hass)
    do_adhoc_statistics(hass, start=period1)
    await async_wait_recording_done(hass)
    do_adhoc_statistics(hass, start=period2)
    await async_wait_recording_done(hass)
    statistic_ids = await hass.async_add_executor_job(list_statistic_ids, hass)
    assert statistic_ids == [
        {
            "statistic_id": "sensor.test1",
            "display_unit_of_measurement": display_unit,
            "has_mean": False,
            "has_sum": True,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": statistics_unit,
        }
    ]
    stats = statistics_during_period(hass, period0, period="5minute")
    expected_stats = {
        "sensor.test1": [
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(period0),
                "end": process_timestamp_to_utc_isoformat(period0_end),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": process_timestamp_to_utc_isoformat(period0),
                "state": approx(factor * seq[2]),
                "sum": approx(factor * 10.0),
            },
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(period1),
                "end": process_timestamp_to_utc_isoformat(period1_end),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": process_timestamp_to_utc_isoformat(four),
                "state": approx(factor * seq[5]),
                "sum": approx(factor * 40.0),
            },
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(period2),
                "end": process_timestamp_to_utc_isoformat(period2_end),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": process_timestamp_to_utc_isoformat(four),
                "state": approx(factor * seq[8]),
                "sum": approx(factor * 70.0),
            },
        ]
    }
    assert stats == expected_stats

    # With an offset of 1 minute, we expect to get all periods
    stats = statistics_during_period(
        hass, period0 + timedelta(minutes=1), period="5minute"
    )
    assert stats == expected_stats

    # With an offset of 5 minutes, we expect to get the 2nd and 3rd periods
    stats = statistics_during_period(
        hass, period0 + timedelta(minutes=5), period="5minute"
    )
    assert stats == {"sensor.test1": expected_stats["sensor.test1"][1:3]}

    # With an offset of 6 minutes, we expect to get the 2nd and 3rd periods
    stats = statistics_during_period(
        hass, period0 + timedelta(minutes=6), period="5minute"
    )
    assert stats == {"sensor.test1": expected_stats["sensor.test1"][1:3]}

    assert "Error while processing event StatisticsTask" not in caplog.text
    assert "Detected new cycle for sensor.test1, last_reset set to" in caplog.text
    assert "Compiling initial sum statistics for sensor.test1" in caplog.text
    assert "Detected new cycle for sensor.test1, value dropped" not in caplog.text

    # Adjust the inserted statistics
    await client.send_json(
        {
            "id": 1,
            "type": "recorder/adjust_sum_statistics",
            "statistic_id": "sensor.test1",
            "start_time": period1.isoformat(),
            "adjustment": 100.0,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    await async_wait_recording_done(hass)

    expected_stats["sensor.test1"][1]["sum"] = approx(factor * 40.0 + 100)
    expected_stats["sensor.test1"][2]["sum"] = approx(factor * 70.0 + 100)
    stats = statistics_during_period(hass, period0, period="5minute")
    assert stats == expected_stats

    # Adjust the inserted statistics
    await client.send_json(
        {
            "id": 2,
            "type": "recorder/adjust_sum_statistics",
            "statistic_id": "sensor.test1",
            "start_time": period2.isoformat(),
            "adjustment": -400.0,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    await async_wait_recording_done(hass)

    expected_stats["sensor.test1"][1]["sum"] = approx(factor * 40.0 + 100)
    expected_stats["sensor.test1"][2]["sum"] = approx(factor * 70.0 - 300)
    stats = statistics_during_period(hass, period0, period="5minute")
    assert stats == expected_stats


@pytest.mark.parametrize("state_class", ["total"])
@pytest.mark.parametrize(
    "device_class,state_unit,display_unit,statistics_unit,factor",
    [
        ("energy", "kWh", "kWh", "kWh", 1),
        ("energy", "Wh", "kWh", "kWh", 1 / 1000),
        ("monetary", "EUR", "EUR", "EUR", 1),
        ("monetary", "SEK", "SEK", "SEK", 1),
        ("gas", "m³", "m³", "m³", 1),
        ("gas", "ft³", "m³", "m³", 0.0283168466),
    ],
)
def test_compile_hourly_sum_statistics_amount_reset_every_state_change(
    hass_recorder,
    caplog,
    state_class,
    device_class,
    state_unit,
    display_unit,
    statistics_unit,
    factor,
):
    """Test compiling hourly statistics."""
    zero = dt_util.utcnow()
    hass = hass_recorder()
    setup_component(hass, "sensor", {})
    wait_recording_done(hass)  # Wait for the sensor recorder platform to be added
    attributes = {
        "device_class": device_class,
        "state_class": state_class,
        "unit_of_measurement": state_unit,
        "last_reset": None,
    }
    seq = [10, 15, 15, 15, 20, 20, 20, 25]
    # Make sure the sequence has consecutive equal states
    assert seq[1] == seq[2] == seq[3]

    # Make sure the first and last state differ
    assert seq[0] != seq[-1]

    states = {"sensor.test1": []}

    # Insert states for a 1st statistics period
    one = zero
    for i in range(len(seq)):
        one = one + timedelta(seconds=5)
        attributes = dict(attributes)
        attributes["last_reset"] = dt_util.as_local(one).isoformat()
        _states = record_meter_state(
            hass, one, "sensor.test1", attributes, seq[i : i + 1]
        )
        states["sensor.test1"].extend(_states["sensor.test1"])

    # Insert states for a 2nd statistics period
    two = zero + timedelta(minutes=5)
    for i in range(len(seq)):
        two = two + timedelta(seconds=5)
        attributes = dict(attributes)
        attributes["last_reset"] = dt_util.as_local(two).isoformat()
        _states = record_meter_state(
            hass, two, "sensor.test1", attributes, seq[i : i + 1]
        )
        states["sensor.test1"].extend(_states["sensor.test1"])

    hist = history.get_significant_states(
        hass,
        zero - timedelta.resolution,
        two + timedelta.resolution,
        significant_changes_only=False,
    )
    assert dict(states)["sensor.test1"] == dict(hist)["sensor.test1"]

    do_adhoc_statistics(hass, start=zero)
    do_adhoc_statistics(hass, start=zero + timedelta(minutes=5))
    wait_recording_done(hass)
    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {
            "statistic_id": "sensor.test1",
            "display_unit_of_measurement": display_unit,
            "has_mean": False,
            "has_sum": True,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": statistics_unit,
        }
    ]
    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {
        "sensor.test1": [
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(zero),
                "end": process_timestamp_to_utc_isoformat(zero + timedelta(minutes=5)),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": process_timestamp_to_utc_isoformat(dt_util.as_local(one)),
                "state": approx(factor * seq[7]),
                "sum": approx(factor * (sum(seq) - seq[0])),
            },
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(
                    zero + timedelta(minutes=5)
                ),
                "end": process_timestamp_to_utc_isoformat(zero + timedelta(minutes=10)),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": process_timestamp_to_utc_isoformat(dt_util.as_local(two)),
                "state": approx(factor * seq[7]),
                "sum": approx(factor * (2 * sum(seq) - seq[0])),
            },
        ]
    }
    assert "Error while processing event StatisticsTask" not in caplog.text


@pytest.mark.parametrize("state_class", ["total"])
@pytest.mark.parametrize(
    "device_class,state_unit,display_unit,statistics_unit,factor",
    [
        ("energy", "kWh", "kWh", "kWh", 1),
    ],
)
def test_compile_hourly_sum_statistics_amount_invalid_last_reset(
    hass_recorder,
    caplog,
    state_class,
    device_class,
    state_unit,
    display_unit,
    statistics_unit,
    factor,
):
    """Test compiling hourly statistics."""
    zero = dt_util.utcnow()
    hass = hass_recorder()
    setup_component(hass, "sensor", {})
    wait_recording_done(hass)  # Wait for the sensor recorder platform to be added
    attributes = {
        "device_class": device_class,
        "state_class": state_class,
        "unit_of_measurement": state_unit,
        "last_reset": None,
    }
    seq = [10, 15, 15, 15, 20, 20, 20, 25]

    states = {"sensor.test1": []}

    # Insert states
    one = zero
    for i in range(len(seq)):
        one = one + timedelta(seconds=5)
        attributes = dict(attributes)
        attributes["last_reset"] = dt_util.as_local(one).isoformat()
        if i == 3:
            attributes["last_reset"] = "festivus"  # not a valid time
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

    do_adhoc_statistics(hass, start=zero)
    wait_recording_done(hass)
    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {
            "statistic_id": "sensor.test1",
            "display_unit_of_measurement": display_unit,
            "has_mean": False,
            "has_sum": True,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": statistics_unit,
        }
    ]
    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {
        "sensor.test1": [
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(zero),
                "end": process_timestamp_to_utc_isoformat(zero + timedelta(minutes=5)),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": process_timestamp_to_utc_isoformat(dt_util.as_local(one)),
                "state": approx(factor * seq[7]),
                "sum": approx(factor * (sum(seq) - seq[0] - seq[3])),
            },
        ]
    }
    assert "Error while processing event StatisticsTask" not in caplog.text
    assert "Ignoring invalid last reset 'festivus' for sensor.test1" in caplog.text


@pytest.mark.parametrize("state_class", ["total"])
@pytest.mark.parametrize(
    "device_class,state_unit,display_unit,statistics_unit,factor",
    [
        ("energy", "kWh", "kWh", "kWh", 1),
    ],
)
def test_compile_hourly_sum_statistics_nan_inf_state(
    hass_recorder,
    caplog,
    state_class,
    device_class,
    state_unit,
    display_unit,
    statistics_unit,
    factor,
):
    """Test compiling hourly statistics with nan and inf states."""
    zero = dt_util.utcnow()
    hass = hass_recorder()
    setup_component(hass, "sensor", {})
    wait_recording_done(hass)  # Wait for the sensor recorder platform to be added
    attributes = {
        "device_class": device_class,
        "state_class": state_class,
        "unit_of_measurement": state_unit,
        "last_reset": None,
    }
    seq = [10, math.nan, 15, 15, 20, math.inf, 20, 10]

    states = {"sensor.test1": []}
    one = zero
    for i in range(len(seq)):
        one = one + timedelta(seconds=5)
        attributes = dict(attributes)
        attributes["last_reset"] = dt_util.as_local(one).isoformat()
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

    do_adhoc_statistics(hass, start=zero)
    wait_recording_done(hass)
    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {
            "statistic_id": "sensor.test1",
            "display_unit_of_measurement": display_unit,
            "has_mean": False,
            "has_sum": True,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": statistics_unit,
        }
    ]
    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {
        "sensor.test1": [
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(zero),
                "end": process_timestamp_to_utc_isoformat(zero + timedelta(minutes=5)),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": process_timestamp_to_utc_isoformat(one),
                "state": approx(factor * seq[7]),
                "sum": approx(factor * (seq[2] + seq[3] + seq[4] + seq[6] + seq[7])),
            },
        ]
    }
    assert "Error while processing event StatisticsTask" not in caplog.text


@pytest.mark.parametrize(
    "entity_id,warning_1,warning_2",
    [
        (
            "sensor.test1",
            "",
            "bug report at https://github.com/home-assistant/core/issues?q=is%3Aopen+is%3Aissue",
        ),
        (
            "sensor.power_consumption",
            "from integration demo ",
            "bug report at https://github.com/home-assistant/core/issues?q=is%3Aopen+is%3Aissue+label%3A%22integration%3A+demo%22",
        ),
        (
            "sensor.custom_sensor",
            "from integration test ",
            "report it to the custom integration author",
        ),
    ],
)
@pytest.mark.parametrize("state_class", ["total_increasing"])
@pytest.mark.parametrize(
    "device_class,state_unit,display_unit,statistics_unit,factor",
    [
        ("energy", "kWh", "kWh", "kWh", 1),
    ],
)
def test_compile_hourly_sum_statistics_negative_state(
    hass_recorder,
    caplog,
    entity_id,
    warning_1,
    warning_2,
    state_class,
    device_class,
    state_unit,
    display_unit,
    statistics_unit,
    factor,
):
    """Test compiling hourly statistics with negative states."""
    zero = dt_util.utcnow()
    hass = hass_recorder()
    hass.data.pop(loader.DATA_CUSTOM_COMPONENTS)

    platform = getattr(hass.components, "test.sensor")
    platform.init(empty=True)
    mocksensor = platform.MockSensor(name="custom_sensor")
    mocksensor._attr_should_poll = False
    platform.ENTITIES["custom_sensor"] = mocksensor

    setup_component(
        hass, "sensor", {"sensor": [{"platform": "demo"}, {"platform": "test"}]}
    )
    hass.block_till_done()
    attributes = {
        "device_class": device_class,
        "state_class": state_class,
        "unit_of_measurement": state_unit,
    }
    seq = [15, 16, 15, 16, 20, -20, 20, 10]

    states = {entity_id: []}
    offending_state = 5
    if state := hass.states.get(entity_id):
        states[entity_id].append(state)
        offending_state = 6
    one = zero
    for i in range(len(seq)):
        one = one + timedelta(seconds=5)
        _states = record_meter_state(hass, one, entity_id, attributes, seq[i : i + 1])
        states[entity_id].extend(_states[entity_id])

    hist = history.get_significant_states(
        hass,
        zero - timedelta.resolution,
        one + timedelta.resolution,
        significant_changes_only=False,
    )
    assert dict(states)[entity_id] == dict(hist)[entity_id]

    do_adhoc_statistics(hass, start=zero)
    wait_recording_done(hass)
    statistic_ids = list_statistic_ids(hass)
    assert {
        "name": None,
        "display_unit_of_measurement": display_unit,
        "has_mean": False,
        "has_sum": True,
        "source": "recorder",
        "statistic_id": entity_id,
        "statistics_unit_of_measurement": statistics_unit,
    } in statistic_ids
    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats[entity_id] == [
        {
            "statistic_id": entity_id,
            "start": process_timestamp_to_utc_isoformat(zero),
            "end": process_timestamp_to_utc_isoformat(zero + timedelta(minutes=5)),
            "max": None,
            "mean": None,
            "min": None,
            "last_reset": None,
            "state": approx(factor * seq[7]),
            "sum": approx(factor * 15),  # (15 - 10) + (10 - 0)
        },
    ]
    assert "Error while processing event StatisticsTask" not in caplog.text
    state = states[entity_id][offending_state].state
    last_updated = states[entity_id][offending_state].last_updated.isoformat()
    assert (
        f"Entity {entity_id} {warning_1}has state class total_increasing, but its state "
        f"is negative. Triggered by state {state} with last_updated set to {last_updated}."
        in caplog.text
    )
    assert warning_2 in caplog.text


@pytest.mark.parametrize(
    "device_class,state_unit,display_unit,statistics_unit,factor",
    [
        ("energy", "kWh", "kWh", "kWh", 1),
        ("energy", "Wh", "kWh", "kWh", 1 / 1000),
        ("monetary", "EUR", "EUR", "EUR", 1),
        ("monetary", "SEK", "SEK", "SEK", 1),
        ("gas", "m³", "m³", "m³", 1),
        ("gas", "ft³", "m³", "m³", 0.0283168466),
    ],
)
def test_compile_hourly_sum_statistics_total_no_reset(
    hass_recorder,
    caplog,
    device_class,
    state_unit,
    display_unit,
    statistics_unit,
    factor,
):
    """Test compiling hourly statistics."""
    period0 = dt_util.utcnow()
    period0_end = period1 = period0 + timedelta(minutes=5)
    period1_end = period2 = period0 + timedelta(minutes=10)
    period2_end = period0 + timedelta(minutes=15)
    hass = hass_recorder()
    setup_component(hass, "sensor", {})
    wait_recording_done(hass)  # Wait for the sensor recorder platform to be added
    attributes = {
        "device_class": device_class,
        "state_class": "total",
        "unit_of_measurement": state_unit,
    }
    seq = [10, 15, 20, 10, 30, 40, 50, 60, 70]

    four, eight, states = record_meter_states(
        hass, period0, "sensor.test1", attributes, seq
    )
    wait_recording_done(hass)
    hist = history.get_significant_states(
        hass, period0 - timedelta.resolution, eight + timedelta.resolution
    )
    assert dict(states)["sensor.test1"] == dict(hist)["sensor.test1"]

    do_adhoc_statistics(hass, start=period0)
    wait_recording_done(hass)
    do_adhoc_statistics(hass, start=period1)
    wait_recording_done(hass)
    do_adhoc_statistics(hass, start=period2)
    wait_recording_done(hass)
    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {
            "statistic_id": "sensor.test1",
            "display_unit_of_measurement": display_unit,
            "has_mean": False,
            "has_sum": True,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": statistics_unit,
        }
    ]
    stats = statistics_during_period(hass, period0, period="5minute")
    assert stats == {
        "sensor.test1": [
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(period0),
                "end": process_timestamp_to_utc_isoformat(period0_end),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": None,
                "state": approx(factor * seq[2]),
                "sum": approx(factor * 10.0),
            },
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(period1),
                "end": process_timestamp_to_utc_isoformat(period1_end),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": None,
                "state": approx(factor * seq[5]),
                "sum": approx(factor * 30.0),
            },
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(period2),
                "end": process_timestamp_to_utc_isoformat(period2_end),
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
    "device_class,state_unit,display_unit,statistics_unit,factor",
    [
        ("energy", "kWh", "kWh", "kWh", 1),
        ("energy", "Wh", "kWh", "kWh", 1 / 1000),
        ("gas", "m³", "m³", "m³", 1),
        ("gas", "ft³", "m³", "m³", 0.0283168466),
    ],
)
def test_compile_hourly_sum_statistics_total_increasing(
    hass_recorder,
    caplog,
    device_class,
    state_unit,
    display_unit,
    statistics_unit,
    factor,
):
    """Test compiling hourly statistics."""
    period0 = dt_util.utcnow()
    period0_end = period1 = period0 + timedelta(minutes=5)
    period1_end = period2 = period0 + timedelta(minutes=10)
    period2_end = period0 + timedelta(minutes=15)
    hass = hass_recorder()
    setup_component(hass, "sensor", {})
    wait_recording_done(hass)  # Wait for the sensor recorder platform to be added
    attributes = {
        "device_class": device_class,
        "state_class": "total_increasing",
        "unit_of_measurement": state_unit,
    }
    seq = [10, 15, 20, 10, 30, 40, 50, 60, 70]

    four, eight, states = record_meter_states(
        hass, period0, "sensor.test1", attributes, seq
    )
    wait_recording_done(hass)
    hist = history.get_significant_states(
        hass, period0 - timedelta.resolution, eight + timedelta.resolution
    )
    assert dict(states)["sensor.test1"] == dict(hist)["sensor.test1"]

    do_adhoc_statistics(hass, start=period0)
    wait_recording_done(hass)
    do_adhoc_statistics(hass, start=period1)
    wait_recording_done(hass)
    do_adhoc_statistics(hass, start=period2)
    wait_recording_done(hass)
    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {
            "statistic_id": "sensor.test1",
            "display_unit_of_measurement": display_unit,
            "has_mean": False,
            "has_sum": True,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": statistics_unit,
        }
    ]
    stats = statistics_during_period(hass, period0, period="5minute")
    assert stats == {
        "sensor.test1": [
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(period0),
                "end": process_timestamp_to_utc_isoformat(period0_end),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": None,
                "state": approx(factor * seq[2]),
                "sum": approx(factor * 10.0),
            },
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(period1),
                "end": process_timestamp_to_utc_isoformat(period1_end),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": None,
                "state": approx(factor * seq[5]),
                "sum": approx(factor * 50.0),
            },
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(period2),
                "end": process_timestamp_to_utc_isoformat(period2_end),
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
    "device_class,state_unit,display_unit,statistics_unit,factor",
    [("energy", "kWh", "kWh", "kWh", 1)],
)
def test_compile_hourly_sum_statistics_total_increasing_small_dip(
    hass_recorder,
    caplog,
    device_class,
    state_unit,
    display_unit,
    statistics_unit,
    factor,
):
    """Test small dips in sensor readings do not trigger a reset."""
    period0 = dt_util.utcnow()
    period0_end = period1 = period0 + timedelta(minutes=5)
    period1_end = period2 = period0 + timedelta(minutes=10)
    period2_end = period0 + timedelta(minutes=15)
    hass = hass_recorder()
    setup_component(hass, "sensor", {})
    wait_recording_done(hass)  # Wait for the sensor recorder platform to be added
    attributes = {
        "device_class": device_class,
        "state_class": "total_increasing",
        "unit_of_measurement": state_unit,
    }
    seq = [10, 15, 20, 19, 30, 40, 39, 60, 70]

    four, eight, states = record_meter_states(
        hass, period0, "sensor.test1", attributes, seq
    )
    wait_recording_done(hass)
    hist = history.get_significant_states(
        hass, period0 - timedelta.resolution, eight + timedelta.resolution
    )
    assert dict(states)["sensor.test1"] == dict(hist)["sensor.test1"]

    do_adhoc_statistics(hass, start=period0)
    wait_recording_done(hass)
    do_adhoc_statistics(hass, start=period1)
    wait_recording_done(hass)
    assert (
        "Entity sensor.test1 has state class total_increasing, but its state is not "
        "strictly increasing."
    ) not in caplog.text
    do_adhoc_statistics(hass, start=period2)
    wait_recording_done(hass)
    state = states["sensor.test1"][6].state
    previous_state = float(states["sensor.test1"][5].state)
    last_updated = states["sensor.test1"][6].last_updated.isoformat()
    assert (
        "Entity sensor.test1 has state class total_increasing, but its state is not "
        f"strictly increasing. Triggered by state {state} ({previous_state}) with "
        f"last_updated set to {last_updated}. Please create a bug report at "
        "https://github.com/home-assistant/core/issues?q=is%3Aopen+is%3Aissue"
    ) in caplog.text
    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {
            "statistic_id": "sensor.test1",
            "display_unit_of_measurement": display_unit,
            "has_mean": False,
            "has_sum": True,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": statistics_unit,
        }
    ]
    stats = statistics_during_period(hass, period0, period="5minute")
    assert stats == {
        "sensor.test1": [
            {
                "last_reset": None,
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(period0),
                "end": process_timestamp_to_utc_isoformat(period0_end),
                "max": None,
                "mean": None,
                "min": None,
                "state": approx(factor * seq[2]),
                "sum": approx(factor * 10.0),
            },
            {
                "last_reset": None,
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(period1),
                "end": process_timestamp_to_utc_isoformat(period1_end),
                "max": None,
                "mean": None,
                "min": None,
                "state": approx(factor * seq[5]),
                "sum": approx(factor * 30.0),
            },
            {
                "last_reset": None,
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(period2),
                "end": process_timestamp_to_utc_isoformat(period2_end),
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
    period0 = dt_util.utcnow()
    period0_end = period1 = period0 + timedelta(minutes=5)
    period1_end = period2 = period0 + timedelta(minutes=10)
    period2_end = period0 + timedelta(minutes=15)
    hass = hass_recorder()
    setup_component(hass, "sensor", {})
    wait_recording_done(hass)  # Wait for the sensor recorder platform to be added
    sns1_attr = {
        "device_class": "energy",
        "state_class": "total",
        "unit_of_measurement": "kWh",
        "last_reset": None,
    }
    sns2_attr = {"device_class": "energy"}
    sns3_attr = {}
    seq1 = [10, 15, 20, 10, 30, 40, 50, 60, 70]
    seq2 = [110, 120, 130, 0, 30, 45, 55, 65, 75]
    seq3 = [0, 0, 5, 10, 30, 50, 60, 80, 90]

    four, eight, states = record_meter_states(
        hass, period0, "sensor.test1", sns1_attr, seq1
    )
    _, _, _states = record_meter_states(hass, period0, "sensor.test2", sns2_attr, seq2)
    states = {**states, **_states}
    _, _, _states = record_meter_states(hass, period0, "sensor.test3", sns3_attr, seq3)
    states = {**states, **_states}
    wait_recording_done(hass)

    hist = history.get_significant_states(
        hass, period0 - timedelta.resolution, eight + timedelta.resolution
    )
    assert dict(states)["sensor.test1"] == dict(hist)["sensor.test1"]

    do_adhoc_statistics(hass, start=period0)
    wait_recording_done(hass)
    do_adhoc_statistics(hass, start=period1)
    wait_recording_done(hass)
    do_adhoc_statistics(hass, start=period2)
    wait_recording_done(hass)
    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {
            "statistic_id": "sensor.test1",
            "display_unit_of_measurement": "kWh",
            "has_mean": False,
            "has_sum": True,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": "kWh",
        }
    ]
    stats = statistics_during_period(hass, period0, period="5minute")
    assert stats == {
        "sensor.test1": [
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(period0),
                "end": process_timestamp_to_utc_isoformat(period0_end),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": process_timestamp_to_utc_isoformat(period0),
                "state": approx(20.0),
                "sum": approx(10.0),
            },
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(period1),
                "end": process_timestamp_to_utc_isoformat(period1_end),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": process_timestamp_to_utc_isoformat(four),
                "state": approx(40.0),
                "sum": approx(40.0),
            },
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(period2),
                "end": process_timestamp_to_utc_isoformat(period2_end),
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
    period0 = dt_util.utcnow()
    period0_end = period1 = period0 + timedelta(minutes=5)
    period1_end = period2 = period0 + timedelta(minutes=10)
    period2_end = period0 + timedelta(minutes=15)
    hass = hass_recorder()
    setup_component(hass, "sensor", {})
    wait_recording_done(hass)  # Wait for the sensor recorder platform to be added
    sns1_attr = {**ENERGY_SENSOR_ATTRIBUTES, "last_reset": None}
    sns2_attr = {**ENERGY_SENSOR_ATTRIBUTES, "last_reset": None}
    sns3_attr = {
        **ENERGY_SENSOR_ATTRIBUTES,
        "unit_of_measurement": "Wh",
        "last_reset": None,
    }
    seq1 = [10, 15, 20, 10, 30, 40, 50, 60, 70]
    seq2 = [110, 120, 130, 0, 30, 45, 55, 65, 75]
    seq3 = [0, 0, 5, 10, 30, 50, 60, 80, 90]

    four, eight, states = record_meter_states(
        hass, period0, "sensor.test1", sns1_attr, seq1
    )
    _, _, _states = record_meter_states(hass, period0, "sensor.test2", sns2_attr, seq2)
    states = {**states, **_states}
    _, _, _states = record_meter_states(hass, period0, "sensor.test3", sns3_attr, seq3)
    states = {**states, **_states}
    wait_recording_done(hass)
    hist = history.get_significant_states(
        hass, period0 - timedelta.resolution, eight + timedelta.resolution
    )
    assert dict(states)["sensor.test1"] == dict(hist)["sensor.test1"]

    do_adhoc_statistics(hass, start=period0)
    wait_recording_done(hass)
    do_adhoc_statistics(hass, start=period1)
    wait_recording_done(hass)
    do_adhoc_statistics(hass, start=period2)
    wait_recording_done(hass)
    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {
            "statistic_id": "sensor.test1",
            "display_unit_of_measurement": "kWh",
            "has_mean": False,
            "has_sum": True,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": "kWh",
        },
        {
            "statistic_id": "sensor.test2",
            "display_unit_of_measurement": "kWh",
            "has_mean": False,
            "has_sum": True,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": "kWh",
        },
        {
            "statistic_id": "sensor.test3",
            "display_unit_of_measurement": "kWh",
            "has_mean": False,
            "has_sum": True,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": "kWh",
        },
    ]
    stats = statistics_during_period(hass, period0, period="5minute")
    assert stats == {
        "sensor.test1": [
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(period0),
                "end": process_timestamp_to_utc_isoformat(period0_end),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": process_timestamp_to_utc_isoformat(period0),
                "state": approx(20.0),
                "sum": approx(10.0),
            },
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(period1),
                "end": process_timestamp_to_utc_isoformat(period1_end),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": process_timestamp_to_utc_isoformat(four),
                "state": approx(40.0),
                "sum": approx(40.0),
            },
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(period2),
                "end": process_timestamp_to_utc_isoformat(period2_end),
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
                "start": process_timestamp_to_utc_isoformat(period0),
                "end": process_timestamp_to_utc_isoformat(period0_end),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": process_timestamp_to_utc_isoformat(period0),
                "state": approx(130.0),
                "sum": approx(20.0),
            },
            {
                "statistic_id": "sensor.test2",
                "start": process_timestamp_to_utc_isoformat(period1),
                "end": process_timestamp_to_utc_isoformat(period1_end),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": process_timestamp_to_utc_isoformat(four),
                "state": approx(45.0),
                "sum": approx(-65.0),
            },
            {
                "statistic_id": "sensor.test2",
                "start": process_timestamp_to_utc_isoformat(period2),
                "end": process_timestamp_to_utc_isoformat(period2_end),
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
                "start": process_timestamp_to_utc_isoformat(period0),
                "end": process_timestamp_to_utc_isoformat(period0_end),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": process_timestamp_to_utc_isoformat(period0),
                "state": approx(5.0 / 1000),
                "sum": approx(5.0 / 1000),
            },
            {
                "statistic_id": "sensor.test3",
                "start": process_timestamp_to_utc_isoformat(period1),
                "end": process_timestamp_to_utc_isoformat(period1_end),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": process_timestamp_to_utc_isoformat(four),
                "state": approx(50.0 / 1000),
                "sum": approx(60.0 / 1000),
            },
            {
                "statistic_id": "sensor.test3",
                "start": process_timestamp_to_utc_isoformat(period2),
                "end": process_timestamp_to_utc_isoformat(period2_end),
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
    "device_class,state_unit,value",
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
    hass_recorder, caplog, device_class, state_unit, value
):
    """Test compiling hourly statistics, with no changes during the hour."""
    zero = dt_util.utcnow()
    hass = hass_recorder()
    setup_component(hass, "sensor", {})
    wait_recording_done(hass)  # Wait for the sensor recorder platform to be added
    attributes = {
        "device_class": device_class,
        "state_class": "measurement",
        "unit_of_measurement": state_unit,
    }
    four, states = record_states(hass, zero, "sensor.test1", attributes)
    hist = history.get_significant_states(hass, zero, four)
    assert dict(states) == dict(hist)

    do_adhoc_statistics(hass, start=four)
    wait_recording_done(hass)
    stats = statistics_during_period(hass, four, period="5minute")
    assert stats == {
        "sensor.test1": [
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(four),
                "end": process_timestamp_to_utc_isoformat(four + timedelta(minutes=5)),
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
    setup_component(hass, "sensor", {})
    wait_recording_done(hass)  # Wait for the sensor recorder platform to be added
    four, states = record_states_partially_unavailable(
        hass, zero, "sensor.test1", TEMPERATURE_SENSOR_ATTRIBUTES
    )
    hist = history.get_significant_states(hass, zero, four)
    assert dict(states) == dict(hist)

    do_adhoc_statistics(hass, start=zero)
    wait_recording_done(hass)
    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {
        "sensor.test1": [
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(zero),
                "end": process_timestamp_to_utc_isoformat(zero + timedelta(minutes=5)),
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
    "device_class,state_unit,value",
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
    hass_recorder, caplog, device_class, state_unit, value
):
    """Test compiling hourly statistics, with the sensor being unavailable."""
    zero = dt_util.utcnow()
    hass = hass_recorder()
    setup_component(hass, "sensor", {})
    wait_recording_done(hass)  # Wait for the sensor recorder platform to be added
    attributes = {
        "device_class": device_class,
        "state_class": "measurement",
        "unit_of_measurement": state_unit,
    }
    four, states = record_states_partially_unavailable(
        hass, zero, "sensor.test1", attributes
    )
    _, _states = record_states(hass, zero, "sensor.test2", attributes)
    states = {**states, **_states}
    hist = history.get_significant_states(hass, zero, four)
    assert dict(states) == dict(hist)

    do_adhoc_statistics(hass, start=four)
    wait_recording_done(hass)
    stats = statistics_during_period(hass, four, period="5minute")
    assert stats == {
        "sensor.test2": [
            {
                "statistic_id": "sensor.test2",
                "start": process_timestamp_to_utc_isoformat(four),
                "end": process_timestamp_to_utc_isoformat(four + timedelta(minutes=5)),
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
    setup_component(hass, "sensor", {})
    wait_recording_done(hass)  # Wait for the sensor recorder platform to be added
    with patch(
        "homeassistant.components.sensor.recorder.compile_statistics",
        side_effect=Exception,
    ):
        do_adhoc_statistics(hass, start=zero)
        wait_recording_done(hass)
    assert "Error while processing event StatisticsTask" in caplog.text


@pytest.mark.parametrize(
    "state_class,device_class,state_unit,display_unit,statistics_unit,statistic_type",
    [
        ("measurement", "battery", "%", "%", "%", "mean"),
        ("measurement", "battery", None, None, None, "mean"),
        ("total", "energy", "Wh", "kWh", "kWh", "sum"),
        ("total", "energy", "kWh", "kWh", "kWh", "sum"),
        ("measurement", "energy", "Wh", "kWh", "kWh", "mean"),
        ("measurement", "energy", "kWh", "kWh", "kWh", "mean"),
        ("measurement", "humidity", "%", "%", "%", "mean"),
        ("measurement", "humidity", None, None, None, "mean"),
        ("total", "monetary", "USD", "USD", "USD", "sum"),
        ("total", "monetary", "None", "None", "None", "sum"),
        ("total", "gas", "m³", "m³", "m³", "sum"),
        ("total", "gas", "ft³", "m³", "m³", "sum"),
        ("measurement", "monetary", "USD", "USD", "USD", "mean"),
        ("measurement", "monetary", "None", "None", "None", "mean"),
        ("measurement", "gas", "m³", "m³", "m³", "mean"),
        ("measurement", "gas", "ft³", "m³", "m³", "mean"),
        ("measurement", "pressure", "Pa", "Pa", "Pa", "mean"),
        ("measurement", "pressure", "hPa", "Pa", "Pa", "mean"),
        ("measurement", "pressure", "mbar", "Pa", "Pa", "mean"),
        ("measurement", "pressure", "inHg", "Pa", "Pa", "mean"),
        ("measurement", "pressure", "psi", "Pa", "Pa", "mean"),
        ("measurement", "temperature", "°C", "°C", "°C", "mean"),
        ("measurement", "temperature", "°F", "°C", "°C", "mean"),
    ],
)
def test_list_statistic_ids(
    hass_recorder,
    caplog,
    state_class,
    device_class,
    state_unit,
    display_unit,
    statistics_unit,
    statistic_type,
):
    """Test listing future statistic ids."""
    hass = hass_recorder()
    setup_component(hass, "sensor", {})
    wait_recording_done(hass)  # Wait for the sensor recorder platform to be added
    attributes = {
        "device_class": device_class,
        "last_reset": 0,
        "state_class": state_class,
        "unit_of_measurement": state_unit,
    }
    hass.states.set("sensor.test1", 0, attributes=attributes)
    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {
            "statistic_id": "sensor.test1",
            "display_unit_of_measurement": display_unit,
            "has_mean": statistic_type == "mean",
            "has_sum": statistic_type == "sum",
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": statistics_unit,
        },
    ]
    for stat_type in ["mean", "sum", "dogs"]:
        statistic_ids = list_statistic_ids(hass, statistic_type=stat_type)
        if statistic_type == stat_type:
            assert statistic_ids == [
                {
                    "statistic_id": "sensor.test1",
                    "display_unit_of_measurement": display_unit,
                    "has_mean": statistic_type == "mean",
                    "has_sum": statistic_type == "sum",
                    "name": None,
                    "source": "recorder",
                    "statistics_unit_of_measurement": statistics_unit,
                },
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
    wait_recording_done(hass)  # Wait for the sensor recorder platform to be added
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
    "device_class,state_unit,display_unit,statistics_unit,mean,min,max",
    [
        (None, None, None, None, 13.050847, -10, 30),
        (None, "%", "%", "%", 13.050847, -10, 30),
        ("battery", "%", "%", "%", 13.050847, -10, 30),
        ("battery", None, None, None, 13.050847, -10, 30),
    ],
)
def test_compile_hourly_statistics_changing_units_1(
    hass_recorder,
    caplog,
    device_class,
    state_unit,
    display_unit,
    statistics_unit,
    mean,
    min,
    max,
):
    """Test compiling hourly statistics where units change from one hour to the next."""
    zero = dt_util.utcnow()
    hass = hass_recorder()
    setup_component(hass, "sensor", {})
    wait_recording_done(hass)  # Wait for the sensor recorder platform to be added
    attributes = {
        "device_class": device_class,
        "state_class": "measurement",
        "unit_of_measurement": state_unit,
    }
    four, states = record_states(hass, zero, "sensor.test1", attributes)
    attributes["unit_of_measurement"] = "cats"
    four, _states = record_states(
        hass, zero + timedelta(minutes=5), "sensor.test1", attributes
    )
    states["sensor.test1"] += _states["sensor.test1"]
    four, _states = record_states(
        hass, zero + timedelta(minutes=10), "sensor.test1", attributes
    )
    states["sensor.test1"] += _states["sensor.test1"]
    hist = history.get_significant_states(hass, zero, four)
    assert dict(states) == dict(hist)

    do_adhoc_statistics(hass, start=zero)
    wait_recording_done(hass)
    assert "does not match the unit of already compiled" not in caplog.text
    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {
            "statistic_id": "sensor.test1",
            "display_unit_of_measurement": display_unit,
            "has_mean": True,
            "has_sum": False,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": statistics_unit,
        },
    ]
    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {
        "sensor.test1": [
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(zero),
                "end": process_timestamp_to_utc_isoformat(zero + timedelta(minutes=5)),
                "mean": approx(mean),
                "min": approx(min),
                "max": approx(max),
                "last_reset": None,
                "state": None,
                "sum": None,
            }
        ]
    }

    do_adhoc_statistics(hass, start=zero + timedelta(minutes=10))
    wait_recording_done(hass)
    assert (
        "The unit of sensor.test1 (cats) does not match the unit of already compiled "
        f"statistics ({display_unit})" in caplog.text
    )
    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {
            "statistic_id": "sensor.test1",
            "display_unit_of_measurement": display_unit,
            "has_mean": True,
            "has_sum": False,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": statistics_unit,
        },
    ]
    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {
        "sensor.test1": [
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(zero),
                "end": process_timestamp_to_utc_isoformat(zero + timedelta(minutes=5)),
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
    "device_class,state_unit,display_unit,statistics_unit,mean,min,max",
    [
        (None, None, None, None, 13.050847, -10, 30),
        (None, "%", "%", "%", 13.050847, -10, 30),
        ("battery", "%", "%", "%", 13.050847, -10, 30),
        ("battery", None, None, None, 13.050847, -10, 30),
    ],
)
def test_compile_hourly_statistics_changing_units_2(
    hass_recorder,
    caplog,
    device_class,
    state_unit,
    display_unit,
    statistics_unit,
    mean,
    min,
    max,
):
    """Test compiling hourly statistics where units change during an hour."""
    zero = dt_util.utcnow()
    hass = hass_recorder()
    setup_component(hass, "sensor", {})
    wait_recording_done(hass)  # Wait for the sensor recorder platform to be added
    attributes = {
        "device_class": device_class,
        "state_class": "measurement",
        "unit_of_measurement": state_unit,
    }
    four, states = record_states(hass, zero, "sensor.test1", attributes)
    attributes["unit_of_measurement"] = "cats"
    four, _states = record_states(
        hass, zero + timedelta(minutes=5), "sensor.test1", attributes
    )
    states["sensor.test1"] += _states["sensor.test1"]
    hist = history.get_significant_states(hass, zero, four)
    assert dict(states) == dict(hist)

    do_adhoc_statistics(hass, start=zero + timedelta(seconds=30 * 5))
    wait_recording_done(hass)
    assert "The unit of sensor.test1 is changing" in caplog.text
    assert "and matches the unit of already compiled statistics" not in caplog.text
    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {
            "statistic_id": "sensor.test1",
            "display_unit_of_measurement": "cats",
            "has_mean": True,
            "has_sum": False,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": "cats",
        },
    ]
    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {}

    assert "Error while processing event StatisticsTask" not in caplog.text


@pytest.mark.parametrize(
    "device_class,state_unit,display_unit,statistics_unit,mean,min,max",
    [
        (None, None, None, None, 13.050847, -10, 30),
        (None, "%", "%", "%", 13.050847, -10, 30),
        ("battery", "%", "%", "%", 13.050847, -10, 30),
        ("battery", None, None, None, 13.050847, -10, 30),
    ],
)
def test_compile_hourly_statistics_changing_units_3(
    hass_recorder,
    caplog,
    device_class,
    state_unit,
    display_unit,
    statistics_unit,
    mean,
    min,
    max,
):
    """Test compiling hourly statistics where units change from one hour to the next."""
    zero = dt_util.utcnow()
    hass = hass_recorder()
    setup_component(hass, "sensor", {})
    wait_recording_done(hass)  # Wait for the sensor recorder platform to be added
    attributes = {
        "device_class": device_class,
        "state_class": "measurement",
        "unit_of_measurement": state_unit,
    }
    four, states = record_states(hass, zero, "sensor.test1", attributes)
    four, _states = record_states(
        hass, zero + timedelta(minutes=5), "sensor.test1", attributes
    )
    states["sensor.test1"] += _states["sensor.test1"]
    attributes["unit_of_measurement"] = "cats"
    four, _states = record_states(
        hass, zero + timedelta(minutes=10), "sensor.test1", attributes
    )
    states["sensor.test1"] += _states["sensor.test1"]
    hist = history.get_significant_states(hass, zero, four)
    assert dict(states) == dict(hist)

    do_adhoc_statistics(hass, start=zero)
    wait_recording_done(hass)
    assert "does not match the unit of already compiled" not in caplog.text
    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {
            "statistic_id": "sensor.test1",
            "display_unit_of_measurement": display_unit,
            "has_mean": True,
            "has_sum": False,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": statistics_unit,
        },
    ]
    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {
        "sensor.test1": [
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(zero),
                "end": process_timestamp_to_utc_isoformat(zero + timedelta(minutes=5)),
                "mean": approx(mean),
                "min": approx(min),
                "max": approx(max),
                "last_reset": None,
                "state": None,
                "sum": None,
            }
        ]
    }

    do_adhoc_statistics(hass, start=zero + timedelta(minutes=10))
    wait_recording_done(hass)
    assert "The unit of sensor.test1 is changing" in caplog.text
    assert (
        f"matches the unit of already compiled statistics ({state_unit})" in caplog.text
    )
    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {
            "statistic_id": "sensor.test1",
            "display_unit_of_measurement": display_unit,
            "has_mean": True,
            "has_sum": False,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": statistics_unit,
        },
    ]
    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {
        "sensor.test1": [
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(zero),
                "end": process_timestamp_to_utc_isoformat(zero + timedelta(minutes=5)),
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
    "device_class,state_unit,statistic_unit,mean,min,max",
    [
        ("power", "kW", "W", 13.050847, -10, 30),
    ],
)
def test_compile_hourly_statistics_changing_device_class_1(
    hass_recorder, caplog, device_class, state_unit, statistic_unit, mean, min, max
):
    """Test compiling hourly statistics where device class changes from one hour to the next."""
    zero = dt_util.utcnow()
    hass = hass_recorder()
    setup_component(hass, "sensor", {})
    wait_recording_done(hass)  # Wait for the sensor recorder platform to be added

    # Record some states for an initial period, the entity has no device class
    attributes = {
        "state_class": "measurement",
        "unit_of_measurement": state_unit,
    }
    four, states = record_states(hass, zero, "sensor.test1", attributes)

    do_adhoc_statistics(hass, start=zero)
    wait_recording_done(hass)
    assert "does not match the unit of already compiled" not in caplog.text
    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {
            "statistic_id": "sensor.test1",
            "display_unit_of_measurement": state_unit,
            "has_mean": True,
            "has_sum": False,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": state_unit,
        },
    ]
    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {
        "sensor.test1": [
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(zero),
                "end": process_timestamp_to_utc_isoformat(zero + timedelta(minutes=5)),
                "mean": approx(mean),
                "min": approx(min),
                "max": approx(max),
                "last_reset": None,
                "state": None,
                "sum": None,
            }
        ]
    }

    # Update device class and record additional states
    attributes["device_class"] = device_class
    four, _states = record_states(
        hass, zero + timedelta(minutes=5), "sensor.test1", attributes
    )
    states["sensor.test1"] += _states["sensor.test1"]
    four, _states = record_states(
        hass, zero + timedelta(minutes=10), "sensor.test1", attributes
    )
    states["sensor.test1"] += _states["sensor.test1"]
    hist = history.get_significant_states(hass, zero, four)
    assert dict(states) == dict(hist)

    # Run statistics again, we get a warning, and no additional statistics is generated
    do_adhoc_statistics(hass, start=zero + timedelta(minutes=10))
    wait_recording_done(hass)
    assert (
        f"The normalized unit of sensor.test1 ({statistic_unit}) does not match the "
        f"unit of already compiled statistics ({state_unit})" in caplog.text
    )
    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {
            "statistic_id": "sensor.test1",
            "display_unit_of_measurement": state_unit,
            "has_mean": True,
            "has_sum": False,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": state_unit,
        },
    ]
    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {
        "sensor.test1": [
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(zero),
                "end": process_timestamp_to_utc_isoformat(zero + timedelta(minutes=5)),
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
    "device_class,state_unit,statistic_unit,mean,min,max",
    [
        ("power", "kW", "W", 13050.847, -10000, 30000),
    ],
)
def test_compile_hourly_statistics_changing_device_class_2(
    hass_recorder, caplog, device_class, state_unit, statistic_unit, mean, min, max
):
    """Test compiling hourly statistics where device class changes from one hour to the next."""
    zero = dt_util.utcnow()
    hass = hass_recorder()
    setup_component(hass, "sensor", {})
    wait_recording_done(hass)  # Wait for the sensor recorder platform to be added

    # Record some states for an initial period, the entity has a device class
    attributes = {
        "device_class": device_class,
        "state_class": "measurement",
        "unit_of_measurement": state_unit,
    }
    four, states = record_states(hass, zero, "sensor.test1", attributes)

    do_adhoc_statistics(hass, start=zero)
    wait_recording_done(hass)
    assert "does not match the unit of already compiled" not in caplog.text
    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {
            "statistic_id": "sensor.test1",
            "display_unit_of_measurement": statistic_unit,
            "has_mean": True,
            "has_sum": False,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": statistic_unit,
        },
    ]
    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {
        "sensor.test1": [
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(zero),
                "end": process_timestamp_to_utc_isoformat(zero + timedelta(minutes=5)),
                "mean": approx(mean),
                "min": approx(min),
                "max": approx(max),
                "last_reset": None,
                "state": None,
                "sum": None,
            }
        ]
    }

    # Remove device class and record additional states
    attributes.pop("device_class")
    four, _states = record_states(
        hass, zero + timedelta(minutes=5), "sensor.test1", attributes
    )
    states["sensor.test1"] += _states["sensor.test1"]
    four, _states = record_states(
        hass, zero + timedelta(minutes=10), "sensor.test1", attributes
    )
    states["sensor.test1"] += _states["sensor.test1"]
    hist = history.get_significant_states(hass, zero, four)
    assert dict(states) == dict(hist)

    # Run statistics again, we get a warning, and no additional statistics is generated
    do_adhoc_statistics(hass, start=zero + timedelta(minutes=10))
    wait_recording_done(hass)
    assert (
        f"The unit of sensor.test1 ({state_unit}) does not match the "
        f"unit of already compiled statistics ({statistic_unit})" in caplog.text
    )
    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {
            "statistic_id": "sensor.test1",
            "display_unit_of_measurement": statistic_unit,
            "has_mean": True,
            "has_sum": False,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": statistic_unit,
        },
    ]
    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {
        "sensor.test1": [
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(zero),
                "end": process_timestamp_to_utc_isoformat(zero + timedelta(minutes=5)),
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
    "device_class,state_unit,display_unit,statistics_unit,mean,min,max",
    [
        (None, None, None, None, 13.050847, -10, 30),
    ],
)
def test_compile_hourly_statistics_changing_statistics(
    hass_recorder,
    caplog,
    device_class,
    state_unit,
    display_unit,
    statistics_unit,
    mean,
    min,
    max,
):
    """Test compiling hourly statistics where units change during an hour."""
    period0 = dt_util.utcnow()
    period0_end = period1 = period0 + timedelta(minutes=5)
    period1_end = period0 + timedelta(minutes=10)
    hass = hass_recorder()
    setup_component(hass, "sensor", {})
    wait_recording_done(hass)  # Wait for the sensor recorder platform to be added
    attributes_1 = {
        "device_class": device_class,
        "state_class": "measurement",
        "unit_of_measurement": state_unit,
    }
    attributes_2 = {
        "device_class": device_class,
        "state_class": "total_increasing",
        "unit_of_measurement": state_unit,
    }
    four, states = record_states(hass, period0, "sensor.test1", attributes_1)
    do_adhoc_statistics(hass, start=period0)
    wait_recording_done(hass)
    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {
            "statistic_id": "sensor.test1",
            "display_unit_of_measurement": None,
            "has_mean": True,
            "has_sum": False,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": None,
        },
    ]
    metadata = get_metadata(hass, statistic_ids=("sensor.test1",))
    assert metadata == {
        "sensor.test1": (
            1,
            {
                "has_mean": True,
                "has_sum": False,
                "name": None,
                "source": "recorder",
                "statistic_id": "sensor.test1",
                "unit_of_measurement": None,
            },
        )
    }

    # Add more states, with changed state class
    four, _states = record_states(hass, period1, "sensor.test1", attributes_2)
    states["sensor.test1"] += _states["sensor.test1"]
    hist = history.get_significant_states(hass, period0, four)
    assert dict(states) == dict(hist)

    do_adhoc_statistics(hass, start=period1)
    wait_recording_done(hass)
    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {
            "statistic_id": "sensor.test1",
            "display_unit_of_measurement": None,
            "has_mean": False,
            "has_sum": True,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": None,
        },
    ]
    metadata = get_metadata(hass, statistic_ids=("sensor.test1",))
    assert metadata == {
        "sensor.test1": (
            1,
            {
                "has_mean": False,
                "has_sum": True,
                "name": None,
                "source": "recorder",
                "statistic_id": "sensor.test1",
                "unit_of_measurement": None,
            },
        )
    }
    stats = statistics_during_period(hass, period0, period="5minute")
    assert stats == {
        "sensor.test1": [
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(period0),
                "end": process_timestamp_to_utc_isoformat(period0_end),
                "mean": approx(mean),
                "min": approx(min),
                "max": approx(max),
                "last_reset": None,
                "state": None,
                "sum": None,
            },
            {
                "statistic_id": "sensor.test1",
                "start": process_timestamp_to_utc_isoformat(period1),
                "end": process_timestamp_to_utc_isoformat(period1_end),
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


def test_compile_statistics_hourly_daily_monthly_summary(hass_recorder, caplog):
    """Test compiling hourly statistics + monthly and daily summary."""
    zero = dt_util.utcnow()
    # August 31st, 23:00 local time
    zero = zero.replace(
        year=2021, month=9, day=1, hour=5, minute=0, second=0, microsecond=0
    )
    with patch(
        "homeassistant.components.recorder.db_schema.dt_util.utcnow", return_value=zero
    ):
        hass = hass_recorder()
        # Remove this after dropping the use of the hass_recorder fixture
        hass.config.set_time_zone("America/Regina")
    instance = get_instance(hass)
    setup_component(hass, "sensor", {})
    wait_recording_done(hass)  # Wait for the sensor recorder platform to be added
    attributes = {
        "device_class": None,
        "state_class": "measurement",
        "unit_of_measurement": "%",
    }

    sum_attributes = {
        "device_class": None,
        "state_class": "total",
        "unit_of_measurement": "EUR",
    }

    def _weighted_average(seq, i, last_state):
        total = 0
        duration = 0
        durations = [50, 200, 45]
        if i > 0:
            total += last_state * 5
            duration += 5
        for j, dur in enumerate(durations):
            total += seq[j] * dur
            duration += dur
        return total / duration

    def _min(seq, last_state):
        if last_state is None:
            return min(seq)
        return min([*seq, last_state])

    def _max(seq, last_state):
        if last_state is None:
            return max(seq)
        return max([*seq, last_state])

    def _sum(seq, last_state, last_sum):
        if last_state is None:
            return seq[-1] - seq[0]
        return last_sum[-1] + seq[-1] - last_state

    # Generate states for two hours
    states = {
        "sensor.test1": [],
        "sensor.test2": [],
        "sensor.test3": [],
        "sensor.test4": [],
    }
    expected_minima = {"sensor.test1": [], "sensor.test2": [], "sensor.test3": []}
    expected_maxima = {"sensor.test1": [], "sensor.test2": [], "sensor.test3": []}
    expected_averages = {"sensor.test1": [], "sensor.test2": [], "sensor.test3": []}
    expected_states = {"sensor.test4": []}
    expected_sums = {"sensor.test4": []}
    last_states = {
        "sensor.test1": None,
        "sensor.test2": None,
        "sensor.test3": None,
        "sensor.test4": None,
    }
    start = zero
    for i in range(24):
        seq = [-10, 15, 30]
        # test1 has same value in every period
        four, _states = record_states(hass, start, "sensor.test1", attributes, seq)
        states["sensor.test1"] += _states["sensor.test1"]
        last_state = last_states["sensor.test1"]
        expected_minima["sensor.test1"].append(_min(seq, last_state))
        expected_maxima["sensor.test1"].append(_max(seq, last_state))
        expected_averages["sensor.test1"].append(_weighted_average(seq, i, last_state))
        last_states["sensor.test1"] = seq[-1]
        # test2 values change: min/max at the last state
        seq = [-10 * (i + 1), 15 * (i + 1), 30 * (i + 1)]
        four, _states = record_states(hass, start, "sensor.test2", attributes, seq)
        states["sensor.test2"] += _states["sensor.test2"]
        last_state = last_states["sensor.test2"]
        expected_minima["sensor.test2"].append(_min(seq, last_state))
        expected_maxima["sensor.test2"].append(_max(seq, last_state))
        expected_averages["sensor.test2"].append(_weighted_average(seq, i, last_state))
        last_states["sensor.test2"] = seq[-1]
        # test3 values change: min/max at the first state
        seq = [-10 * (23 - i + 1), 15 * (23 - i + 1), 30 * (23 - i + 1)]
        four, _states = record_states(hass, start, "sensor.test3", attributes, seq)
        states["sensor.test3"] += _states["sensor.test3"]
        last_state = last_states["sensor.test3"]
        expected_minima["sensor.test3"].append(_min(seq, last_state))
        expected_maxima["sensor.test3"].append(_max(seq, last_state))
        expected_averages["sensor.test3"].append(_weighted_average(seq, i, last_state))
        last_states["sensor.test3"] = seq[-1]
        # test4 values grow
        seq = [i, i + 0.5, i + 0.75]
        start_meter = start
        for j in range(len(seq)):
            _states = record_meter_state(
                hass,
                start_meter,
                "sensor.test4",
                sum_attributes,
                seq[j : j + 1],
            )
            start_meter = start + timedelta(minutes=1)
            states["sensor.test4"] += _states["sensor.test4"]
        last_state = last_states["sensor.test4"]
        expected_states["sensor.test4"].append(seq[-1])
        expected_sums["sensor.test4"].append(
            _sum(seq, last_state, expected_sums["sensor.test4"])
        )
        last_states["sensor.test4"] = seq[-1]

        start += timedelta(minutes=5)
    hist = history.get_significant_states(
        hass, zero - timedelta.resolution, four, significant_changes_only=False
    )
    assert dict(states) == dict(hist)
    wait_recording_done(hass)

    # Generate 5-minute statistics for two hours
    start = zero
    for i in range(24):
        do_adhoc_statistics(hass, start=start)
        wait_recording_done(hass)
        start += timedelta(minutes=5)

    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {
            "statistic_id": "sensor.test1",
            "display_unit_of_measurement": "%",
            "has_mean": True,
            "has_sum": False,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": "%",
        },
        {
            "statistic_id": "sensor.test2",
            "display_unit_of_measurement": "%",
            "has_mean": True,
            "has_sum": False,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": "%",
        },
        {
            "statistic_id": "sensor.test3",
            "display_unit_of_measurement": "%",
            "has_mean": True,
            "has_sum": False,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": "%",
        },
        {
            "statistic_id": "sensor.test4",
            "display_unit_of_measurement": "EUR",
            "has_mean": False,
            "has_sum": True,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": "EUR",
        },
    ]

    # Adjust the inserted statistics
    sum_adjustment = -10
    sum_adjustement_start = zero + timedelta(minutes=65)
    for i in range(13, 24):
        expected_sums["sensor.test4"][i] += sum_adjustment
    instance.async_adjust_statistics(
        "sensor.test4", sum_adjustement_start, sum_adjustment
    )
    wait_recording_done(hass)

    stats = statistics_during_period(hass, zero, period="5minute")
    expected_stats = {
        "sensor.test1": [],
        "sensor.test2": [],
        "sensor.test3": [],
        "sensor.test4": [],
    }
    start = zero
    end = zero + timedelta(minutes=5)
    for i in range(24):
        for entity_id in [
            "sensor.test1",
            "sensor.test2",
            "sensor.test3",
            "sensor.test4",
        ]:
            expected_average = (
                expected_averages[entity_id][i]
                if entity_id in expected_averages
                else None
            )
            expected_minimum = (
                expected_minima[entity_id][i] if entity_id in expected_minima else None
            )
            expected_maximum = (
                expected_maxima[entity_id][i] if entity_id in expected_maxima else None
            )
            expected_state = (
                expected_states[entity_id][i] if entity_id in expected_states else None
            )
            expected_sum = (
                expected_sums[entity_id][i] if entity_id in expected_sums else None
            )
            expected_stats[entity_id].append(
                {
                    "statistic_id": entity_id,
                    "start": process_timestamp_to_utc_isoformat(start),
                    "end": process_timestamp_to_utc_isoformat(end),
                    "mean": approx(expected_average),
                    "min": approx(expected_minimum),
                    "max": approx(expected_maximum),
                    "last_reset": None,
                    "state": expected_state,
                    "sum": expected_sum,
                }
            )
        start += timedelta(minutes=5)
        end += timedelta(minutes=5)
    assert stats == expected_stats

    stats = statistics_during_period(hass, zero, period="hour")
    expected_stats = {
        "sensor.test1": [],
        "sensor.test2": [],
        "sensor.test3": [],
        "sensor.test4": [],
    }
    start = zero
    end = zero + timedelta(hours=1)
    for i in range(2):
        for entity_id in [
            "sensor.test1",
            "sensor.test2",
            "sensor.test3",
            "sensor.test4",
        ]:
            expected_average = (
                mean(expected_averages[entity_id][i * 12 : (i + 1) * 12])
                if entity_id in expected_averages
                else None
            )
            expected_minimum = (
                min(expected_minima[entity_id][i * 12 : (i + 1) * 12])
                if entity_id in expected_minima
                else None
            )
            expected_maximum = (
                max(expected_maxima[entity_id][i * 12 : (i + 1) * 12])
                if entity_id in expected_maxima
                else None
            )
            expected_state = (
                expected_states[entity_id][(i + 1) * 12 - 1]
                if entity_id in expected_states
                else None
            )
            expected_sum = (
                expected_sums[entity_id][(i + 1) * 12 - 1]
                if entity_id in expected_sums
                else None
            )
            expected_stats[entity_id].append(
                {
                    "statistic_id": entity_id,
                    "start": process_timestamp_to_utc_isoformat(start),
                    "end": process_timestamp_to_utc_isoformat(end),
                    "mean": approx(expected_average),
                    "min": approx(expected_minimum),
                    "max": approx(expected_maximum),
                    "last_reset": None,
                    "state": expected_state,
                    "sum": expected_sum,
                }
            )
        start += timedelta(hours=1)
        end += timedelta(hours=1)
    assert stats == expected_stats

    stats = statistics_during_period(hass, zero, period="day")
    expected_stats = {
        "sensor.test1": [],
        "sensor.test2": [],
        "sensor.test3": [],
        "sensor.test4": [],
    }
    start = dt_util.parse_datetime("2021-08-31T06:00:00+00:00")
    end = start + timedelta(days=1)
    for i in range(2):
        for entity_id in [
            "sensor.test1",
            "sensor.test2",
            "sensor.test3",
            "sensor.test4",
        ]:
            expected_average = (
                mean(expected_averages[entity_id][i * 12 : (i + 1) * 12])
                if entity_id in expected_averages
                else None
            )
            expected_minimum = (
                min(expected_minima[entity_id][i * 12 : (i + 1) * 12])
                if entity_id in expected_minima
                else None
            )
            expected_maximum = (
                max(expected_maxima[entity_id][i * 12 : (i + 1) * 12])
                if entity_id in expected_maxima
                else None
            )
            expected_state = (
                expected_states[entity_id][(i + 1) * 12 - 1]
                if entity_id in expected_states
                else None
            )
            expected_sum = (
                expected_sums[entity_id][(i + 1) * 12 - 1]
                if entity_id in expected_sums
                else None
            )
            expected_stats[entity_id].append(
                {
                    "statistic_id": entity_id,
                    "start": process_timestamp_to_utc_isoformat(start),
                    "end": process_timestamp_to_utc_isoformat(end),
                    "mean": approx(expected_average),
                    "min": approx(expected_minimum),
                    "max": approx(expected_maximum),
                    "last_reset": None,
                    "state": expected_state,
                    "sum": expected_sum,
                }
            )
        start += timedelta(days=1)
        end += timedelta(days=1)
    assert stats == expected_stats

    stats = statistics_during_period(hass, zero, period="month")
    expected_stats = {
        "sensor.test1": [],
        "sensor.test2": [],
        "sensor.test3": [],
        "sensor.test4": [],
    }
    start = dt_util.parse_datetime("2021-08-01T06:00:00+00:00")
    end = dt_util.parse_datetime("2021-09-01T06:00:00+00:00")
    for i in range(2):
        for entity_id in [
            "sensor.test1",
            "sensor.test2",
            "sensor.test3",
            "sensor.test4",
        ]:
            expected_average = (
                mean(expected_averages[entity_id][i * 12 : (i + 1) * 12])
                if entity_id in expected_averages
                else None
            )
            expected_minimum = (
                min(expected_minima[entity_id][i * 12 : (i + 1) * 12])
                if entity_id in expected_minima
                else None
            )
            expected_maximum = (
                max(expected_maxima[entity_id][i * 12 : (i + 1) * 12])
                if entity_id in expected_maxima
                else None
            )
            expected_state = (
                expected_states[entity_id][(i + 1) * 12 - 1]
                if entity_id in expected_states
                else None
            )
            expected_sum = (
                expected_sums[entity_id][(i + 1) * 12 - 1]
                if entity_id in expected_sums
                else None
            )
            expected_stats[entity_id].append(
                {
                    "statistic_id": entity_id,
                    "start": process_timestamp_to_utc_isoformat(start),
                    "end": process_timestamp_to_utc_isoformat(end),
                    "mean": approx(expected_average),
                    "min": approx(expected_minimum),
                    "max": approx(expected_maximum),
                    "last_reset": None,
                    "state": expected_state,
                    "sum": expected_sum,
                }
            )
        start = (start + timedelta(days=31)).replace(day=1)
        end = (end + timedelta(days=31)).replace(day=1)
    assert stats == expected_stats

    assert "Error while processing event StatisticsTask" not in caplog.text


def record_states(hass, zero, entity_id, attributes, seq=None):
    """Record some test states.

    We inject a bunch of state updates for measurement sensors.
    """
    attributes = dict(attributes)
    if seq is None:
        seq = [-10, 15, 30]

    def set_state(entity_id, state, **kwargs):
        """Set the state."""
        hass.states.set(entity_id, state, **kwargs)
        wait_recording_done(hass)
        return hass.states.get(entity_id)

    one = zero + timedelta(seconds=1 * 5)
    two = one + timedelta(seconds=10 * 5)
    three = two + timedelta(seconds=40 * 5)
    four = three + timedelta(seconds=10 * 5)

    states = {entity_id: []}
    with patch(
        "homeassistant.components.recorder.core.dt_util.utcnow", return_value=one
    ):
        states[entity_id].append(
            set_state(entity_id, str(seq[0]), attributes=attributes)
        )

    with patch(
        "homeassistant.components.recorder.core.dt_util.utcnow", return_value=two
    ):
        states[entity_id].append(
            set_state(entity_id, str(seq[1]), attributes=attributes)
        )

    with patch(
        "homeassistant.components.recorder.core.dt_util.utcnow", return_value=three
    ):
        states[entity_id].append(
            set_state(entity_id, str(seq[2]), attributes=attributes)
        )

    return four, states


@pytest.mark.parametrize(
    "units, attributes, unit",
    [
        (IMPERIAL_SYSTEM, POWER_SENSOR_ATTRIBUTES, "W"),
        (METRIC_SYSTEM, POWER_SENSOR_ATTRIBUTES, "W"),
        (IMPERIAL_SYSTEM, TEMPERATURE_SENSOR_ATTRIBUTES, "°F"),
        (METRIC_SYSTEM, TEMPERATURE_SENSOR_ATTRIBUTES, "°C"),
        (IMPERIAL_SYSTEM, PRESSURE_SENSOR_ATTRIBUTES, "psi"),
        (METRIC_SYSTEM, PRESSURE_SENSOR_ATTRIBUTES, "Pa"),
    ],
)
async def test_validate_statistics_supported_device_class(
    hass, hass_ws_client, recorder_mock, units, attributes, unit
):
    """Test validate_statistics."""
    id = 1

    def next_id():
        nonlocal id
        id += 1
        return id

    async def assert_validation_result(client, expected_result):
        await client.send_json(
            {"id": next_id(), "type": "recorder/validate_statistics"}
        )
        response = await client.receive_json()
        assert response["success"]
        assert response["result"] == expected_result

    now = dt_util.utcnow()

    hass.config.units = units
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)
    client = await hass_ws_client()

    # No statistics, no state - empty response
    await assert_validation_result(client, {})

    # No statistics, valid state - empty response
    hass.states.async_set(
        "sensor.test", 10, attributes={**attributes, **{"unit_of_measurement": unit}}
    )
    await async_recorder_block_till_done(hass)
    await assert_validation_result(client, {})

    # No statistics, invalid state - expect error
    hass.states.async_set(
        "sensor.test", 11, attributes={**attributes, **{"unit_of_measurement": "dogs"}}
    )
    await async_recorder_block_till_done(hass)
    expected = {
        "sensor.test": [
            {
                "data": {
                    "device_class": attributes["device_class"],
                    "state_unit": "dogs",
                    "statistic_id": "sensor.test",
                },
                "type": "unsupported_unit_state",
            }
        ],
    }
    await assert_validation_result(client, expected)

    # Statistics has run, invalid state - expect error
    await async_recorder_block_till_done(hass)
    do_adhoc_statistics(hass, start=now)
    hass.states.async_set(
        "sensor.test", 12, attributes={**attributes, **{"unit_of_measurement": "dogs"}}
    )
    await async_recorder_block_till_done(hass)
    await assert_validation_result(client, expected)

    # Valid state - empty response
    hass.states.async_set(
        "sensor.test", 13, attributes={**attributes, **{"unit_of_measurement": unit}}
    )
    await async_recorder_block_till_done(hass)
    await assert_validation_result(client, {})

    # Valid state, statistic runs again - empty response
    do_adhoc_statistics(hass, start=now)
    await async_recorder_block_till_done(hass)
    await assert_validation_result(client, {})

    # Remove the state - empty response
    hass.states.async_remove("sensor.test")
    expected = {
        "sensor.test": [
            {
                "data": {"statistic_id": "sensor.test"},
                "type": "no_state",
            }
        ],
    }
    await assert_validation_result(client, expected)


@pytest.mark.parametrize(
    "units, attributes, unit",
    [
        (IMPERIAL_SYSTEM, POWER_SENSOR_ATTRIBUTES, "W"),
    ],
)
async def test_validate_statistics_supported_device_class_2(
    hass, hass_ws_client, recorder_mock, units, attributes, unit
):
    """Test validate_statistics."""
    id = 1

    def next_id():
        nonlocal id
        id += 1
        return id

    async def assert_validation_result(client, expected_result):
        await client.send_json(
            {"id": next_id(), "type": "recorder/validate_statistics"}
        )
        response = await client.receive_json()
        assert response["success"]
        assert response["result"] == expected_result

    now = dt_util.utcnow()

    hass.config.units = units
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)
    client = await hass_ws_client()

    # No statistics, no state - empty response
    await assert_validation_result(client, {})

    # No statistics, valid state - empty response
    initial_attributes = {"state_class": "measurement"}
    hass.states.async_set("sensor.test", 10, attributes=initial_attributes)
    await hass.async_block_till_done()
    await assert_validation_result(client, {})

    # Statistics has run, device class set - expect error
    do_adhoc_statistics(hass, start=now)
    await async_recorder_block_till_done(hass)
    hass.states.async_set("sensor.test", 12, attributes=attributes)
    await hass.async_block_till_done()
    expected = {
        "sensor.test": [
            {
                "data": {
                    "device_class": attributes["device_class"],
                    "metadata_unit": None,
                    "statistic_id": "sensor.test",
                    "supported_unit": unit,
                },
                "type": "unsupported_unit_metadata",
            }
        ],
    }
    await assert_validation_result(client, expected)

    # Invalid state too, expect double errors
    hass.states.async_set(
        "sensor.test", 13, attributes={**attributes, **{"unit_of_measurement": "dogs"}}
    )
    await async_recorder_block_till_done(hass)
    expected = {
        "sensor.test": [
            {
                "data": {
                    "device_class": attributes["device_class"],
                    "metadata_unit": None,
                    "statistic_id": "sensor.test",
                    "supported_unit": unit,
                },
                "type": "unsupported_unit_metadata",
            },
            {
                "data": {
                    "device_class": attributes["device_class"],
                    "state_unit": "dogs",
                    "statistic_id": "sensor.test",
                },
                "type": "unsupported_unit_state",
            },
        ],
    }
    await assert_validation_result(client, expected)


@pytest.mark.parametrize(
    "units, attributes, unit",
    [
        (IMPERIAL_SYSTEM, POWER_SENSOR_ATTRIBUTES, "W"),
    ],
)
async def test_validate_statistics_unsupported_state_class(
    hass, hass_ws_client, recorder_mock, units, attributes, unit
):
    """Test validate_statistics."""
    id = 1

    def next_id():
        nonlocal id
        id += 1
        return id

    async def assert_validation_result(client, expected_result):
        await client.send_json(
            {"id": next_id(), "type": "recorder/validate_statistics"}
        )
        response = await client.receive_json()
        assert response["success"]
        assert response["result"] == expected_result

    now = dt_util.utcnow()

    hass.config.units = units
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)
    client = await hass_ws_client()

    # No statistics, no state - empty response
    await assert_validation_result(client, {})

    # No statistics, valid state - empty response
    hass.states.async_set("sensor.test", 10, attributes=attributes)
    await hass.async_block_till_done()
    await assert_validation_result(client, {})

    # Statistics has run, empty response
    do_adhoc_statistics(hass, start=now)
    await async_recorder_block_till_done(hass)
    await assert_validation_result(client, {})

    # State update with invalid state class, expect error
    _attributes = dict(attributes)
    _attributes.pop("state_class")
    hass.states.async_set("sensor.test", 12, attributes=_attributes)
    await hass.async_block_till_done()
    expected = {
        "sensor.test": [
            {
                "data": {
                    "state_class": None,
                    "statistic_id": "sensor.test",
                },
                "type": "unsupported_state_class",
            }
        ],
    }
    await assert_validation_result(client, expected)


@pytest.mark.parametrize(
    "units, attributes, unit",
    [
        (IMPERIAL_SYSTEM, POWER_SENSOR_ATTRIBUTES, "W"),
    ],
)
async def test_validate_statistics_sensor_no_longer_recorded(
    hass, hass_ws_client, recorder_mock, units, attributes, unit
):
    """Test validate_statistics."""
    id = 1

    def next_id():
        nonlocal id
        id += 1
        return id

    async def assert_validation_result(client, expected_result):
        await client.send_json(
            {"id": next_id(), "type": "recorder/validate_statistics"}
        )
        response = await client.receive_json()
        assert response["success"]
        assert response["result"] == expected_result

    now = dt_util.utcnow()

    hass.config.units = units
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)
    client = await hass_ws_client()

    # No statistics, no state - empty response
    await assert_validation_result(client, {})

    # No statistics, valid state - empty response
    hass.states.async_set("sensor.test", 10, attributes=attributes)
    await hass.async_block_till_done()
    await assert_validation_result(client, {})

    # Statistics has run, empty response
    do_adhoc_statistics(hass, start=now)
    await async_recorder_block_till_done(hass)
    await assert_validation_result(client, {})

    # Sensor no longer recorded, expect error
    expected = {
        "sensor.test": [
            {
                "data": {"statistic_id": "sensor.test"},
                "type": "entity_no_longer_recorded",
            }
        ],
    }
    with patch(
        "homeassistant.components.sensor.recorder.is_entity_recorded",
        return_value=False,
    ):
        await assert_validation_result(client, expected)


@pytest.mark.parametrize(
    "units, attributes, unit",
    [
        (IMPERIAL_SYSTEM, POWER_SENSOR_ATTRIBUTES, "W"),
    ],
)
async def test_validate_statistics_sensor_not_recorded(
    hass, hass_ws_client, recorder_mock, units, attributes, unit
):
    """Test validate_statistics."""
    id = 1

    def next_id():
        nonlocal id
        id += 1
        return id

    async def assert_validation_result(client, expected_result):
        await client.send_json(
            {"id": next_id(), "type": "recorder/validate_statistics"}
        )
        response = await client.receive_json()
        assert response["success"]
        assert response["result"] == expected_result

    now = dt_util.utcnow()

    hass.config.units = units
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)
    client = await hass_ws_client()

    # No statistics, no state - empty response
    await assert_validation_result(client, {})

    # Sensor not recorded, expect error
    expected = {
        "sensor.test": [
            {
                "data": {"statistic_id": "sensor.test"},
                "type": "entity_not_recorded",
            }
        ],
    }
    with patch(
        "homeassistant.components.sensor.recorder.is_entity_recorded",
        return_value=False,
    ):
        hass.states.async_set("sensor.test", 10, attributes=attributes)
        await hass.async_block_till_done()
        await assert_validation_result(client, expected)

        # Statistics has run, expect same error
        do_adhoc_statistics(hass, start=now)
        await async_recorder_block_till_done(hass)
        await assert_validation_result(client, expected)


@pytest.mark.parametrize(
    "units, attributes, unit",
    [
        (IMPERIAL_SYSTEM, POWER_SENSOR_ATTRIBUTES, "W"),
    ],
)
async def test_validate_statistics_sensor_removed(
    hass, hass_ws_client, recorder_mock, units, attributes, unit
):
    """Test validate_statistics."""
    id = 1

    def next_id():
        nonlocal id
        id += 1
        return id

    async def assert_validation_result(client, expected_result):
        await client.send_json(
            {"id": next_id(), "type": "recorder/validate_statistics"}
        )
        response = await client.receive_json()
        assert response["success"]
        assert response["result"] == expected_result

    now = dt_util.utcnow()

    hass.config.units = units
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)
    client = await hass_ws_client()

    # No statistics, no state - empty response
    await assert_validation_result(client, {})

    # No statistics, valid state - empty response
    hass.states.async_set("sensor.test", 10, attributes=attributes)
    await hass.async_block_till_done()
    await assert_validation_result(client, {})

    # Statistics has run, empty response
    do_adhoc_statistics(hass, start=now)
    await async_recorder_block_till_done(hass)
    await assert_validation_result(client, {})

    # Sensor removed, expect error
    hass.states.async_remove("sensor.test")
    expected = {
        "sensor.test": [
            {
                "data": {"statistic_id": "sensor.test"},
                "type": "no_state",
            }
        ],
    }
    await assert_validation_result(client, expected)


@pytest.mark.parametrize(
    "attributes",
    [BATTERY_SENSOR_ATTRIBUTES, NONE_SENSOR_ATTRIBUTES],
)
async def test_validate_statistics_unsupported_device_class(
    hass, recorder_mock, hass_ws_client, attributes
):
    """Test validate_statistics."""
    id = 1

    def next_id():
        nonlocal id
        id += 1
        return id

    async def assert_validation_result(client, expected_result):
        await client.send_json(
            {"id": next_id(), "type": "recorder/validate_statistics"}
        )
        response = await client.receive_json()
        assert response["success"]
        assert response["result"] == expected_result

    async def assert_statistic_ids(expected_result):
        with session_scope(hass=hass) as session:
            db_states = list(session.query(StatisticsMeta))
            assert len(db_states) == len(expected_result)
            for i in range(len(db_states)):
                assert db_states[i].statistic_id == expected_result[i]["statistic_id"]
                assert (
                    db_states[i].unit_of_measurement
                    == expected_result[i]["unit_of_measurement"]
                )

    now = dt_util.utcnow()

    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)
    client = await hass_ws_client()

    # No statistics, no state - empty response
    await assert_validation_result(client, {})

    # No statistics, original unit - empty response
    hass.states.async_set("sensor.test", 10, attributes=attributes)
    await assert_validation_result(client, {})

    # No statistics, changed unit - empty response
    hass.states.async_set(
        "sensor.test", 11, attributes={**attributes, **{"unit_of_measurement": "dogs"}}
    )
    await assert_validation_result(client, {})

    # Run statistics, no statistics will be generated because of conflicting units
    await async_recorder_block_till_done(hass)
    do_adhoc_statistics(hass, start=now)
    await async_recorder_block_till_done(hass)
    await assert_statistic_ids([])

    # No statistics, changed unit - empty response
    hass.states.async_set(
        "sensor.test", 12, attributes={**attributes, **{"unit_of_measurement": "dogs"}}
    )
    await assert_validation_result(client, {})

    # Run statistics one hour later, only the "dogs" state will be considered
    await async_recorder_block_till_done(hass)
    do_adhoc_statistics(hass, start=now + timedelta(hours=1))
    await async_recorder_block_till_done(hass)
    await assert_statistic_ids(
        [{"statistic_id": "sensor.test", "unit_of_measurement": "dogs"}]
    )
    await assert_validation_result(client, {})

    # Change back to original unit - expect error
    hass.states.async_set("sensor.test", 13, attributes=attributes)
    await async_recorder_block_till_done(hass)
    expected = {
        "sensor.test": [
            {
                "data": {
                    "metadata_unit": "dogs",
                    "state_unit": attributes.get("unit_of_measurement"),
                    "statistic_id": "sensor.test",
                },
                "type": "units_changed",
            }
        ],
    }
    await assert_validation_result(client, expected)

    # Changed unit - empty response
    hass.states.async_set(
        "sensor.test", 14, attributes={**attributes, **{"unit_of_measurement": "dogs"}}
    )
    await async_recorder_block_till_done(hass)
    await assert_validation_result(client, {})

    # Valid state, statistic runs again - empty response
    await async_recorder_block_till_done(hass)
    do_adhoc_statistics(hass, start=now)
    await async_recorder_block_till_done(hass)
    await assert_validation_result(client, {})

    # Remove the state - empty response
    hass.states.async_remove("sensor.test")
    expected = {
        "sensor.test": [
            {
                "data": {"statistic_id": "sensor.test"},
                "type": "no_state",
            }
        ],
    }
    await assert_validation_result(client, expected)


def record_meter_states(hass, zero, entity_id, _attributes, seq):
    """Record some test states.

    We inject a bunch of state updates for meter sensors.
    """

    def set_state(entity_id, state, **kwargs):
        """Set the state."""
        hass.states.set(entity_id, state, **kwargs)
        return hass.states.get(entity_id)

    one = zero + timedelta(seconds=15 * 5)  # 00:01:15
    two = one + timedelta(seconds=30 * 5)  # 00:03:45
    three = two + timedelta(seconds=15 * 5)  # 00:05:00
    four = three + timedelta(seconds=15 * 5)  # 00:06:15
    five = four + timedelta(seconds=30 * 5)  # 00:08:45
    six = five + timedelta(seconds=15 * 5)  # 00:10:00
    seven = six + timedelta(seconds=15 * 5)  # 00:11:45
    eight = seven + timedelta(seconds=30 * 5)  # 00:13:45

    attributes = dict(_attributes)
    if "last_reset" in _attributes:
        attributes["last_reset"] = zero.isoformat()

    states = {entity_id: []}
    with patch(
        "homeassistant.components.recorder.core.dt_util.utcnow", return_value=zero
    ):
        states[entity_id].append(set_state(entity_id, seq[0], attributes=attributes))

    with patch(
        "homeassistant.components.recorder.core.dt_util.utcnow", return_value=one
    ):
        states[entity_id].append(set_state(entity_id, seq[1], attributes=attributes))

    with patch(
        "homeassistant.components.recorder.core.dt_util.utcnow", return_value=two
    ):
        states[entity_id].append(set_state(entity_id, seq[2], attributes=attributes))

    with patch(
        "homeassistant.components.recorder.core.dt_util.utcnow", return_value=three
    ):
        states[entity_id].append(set_state(entity_id, seq[3], attributes=attributes))

    attributes = dict(_attributes)
    if "last_reset" in _attributes:
        attributes["last_reset"] = four.isoformat()

    with patch(
        "homeassistant.components.recorder.core.dt_util.utcnow", return_value=four
    ):
        states[entity_id].append(set_state(entity_id, seq[4], attributes=attributes))

    with patch(
        "homeassistant.components.recorder.core.dt_util.utcnow", return_value=five
    ):
        states[entity_id].append(set_state(entity_id, seq[5], attributes=attributes))

    with patch(
        "homeassistant.components.recorder.core.dt_util.utcnow", return_value=six
    ):
        states[entity_id].append(set_state(entity_id, seq[6], attributes=attributes))

    with patch(
        "homeassistant.components.recorder.core.dt_util.utcnow", return_value=seven
    ):
        states[entity_id].append(set_state(entity_id, seq[7], attributes=attributes))

    with patch(
        "homeassistant.components.recorder.core.dt_util.utcnow", return_value=eight
    ):
        states[entity_id].append(set_state(entity_id, seq[8], attributes=attributes))

    return four, eight, states


def record_meter_state(hass, zero, entity_id, attributes, seq):
    """Record test state.

    We inject a state update for meter sensor.
    """

    def set_state(entity_id, state, **kwargs):
        """Set the state."""
        hass.states.set(entity_id, state, **kwargs)
        wait_recording_done(hass)
        return hass.states.get(entity_id)

    states = {entity_id: []}
    with patch(
        "homeassistant.components.recorder.core.dt_util.utcnow", return_value=zero
    ):
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

    one = zero + timedelta(seconds=1 * 5)
    two = one + timedelta(seconds=15 * 5)
    three = two + timedelta(seconds=30 * 5)
    four = three + timedelta(seconds=15 * 5)

    states = {entity_id: []}
    with patch(
        "homeassistant.components.recorder.core.dt_util.utcnow", return_value=one
    ):
        states[entity_id].append(set_state(entity_id, "10", attributes=attributes))

    with patch(
        "homeassistant.components.recorder.core.dt_util.utcnow", return_value=two
    ):
        states[entity_id].append(set_state(entity_id, "25", attributes=attributes))

    with patch(
        "homeassistant.components.recorder.core.dt_util.utcnow", return_value=three
    ):
        states[entity_id].append(
            set_state(entity_id, STATE_UNAVAILABLE, attributes=attributes)
        )

    return four, states
