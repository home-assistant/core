"""The tests for sensor recorder platform."""
from collections.abc import Callable
from datetime import datetime, timedelta
import math
from statistics import mean
from unittest.mock import patch

from freezegun import freeze_time
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant import loader
from homeassistant.components.recorder import (
    DOMAIN as RECORDER_DOMAIN,
    Recorder,
    history,
)
from homeassistant.components.recorder.db_schema import (
    StateAttributes,
    States,
    StatesMeta,
    StatisticsMeta,
)
from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMetaData,
    process_timestamp,
)
from homeassistant.components.recorder.statistics import (
    async_import_statistics,
    get_metadata,
    list_statistic_ids,
)
from homeassistant.components.recorder.util import get_instance, session_scope
from homeassistant.components.sensor import ATTR_OPTIONS, SensorDeviceClass
from homeassistant.const import ATTR_FRIENDLY_NAME, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant, State
from homeassistant.setup import async_setup_component, setup_component
import homeassistant.util.dt as dt_util
from homeassistant.util.unit_system import METRIC_SYSTEM, US_CUSTOMARY_SYSTEM

from tests.components.recorder.common import (
    assert_dict_of_states_equal_without_context_and_last_changed,
    assert_multiple_states_equal_without_context_and_last_changed,
    async_recorder_block_till_done,
    async_wait_recording_done,
    do_adhoc_statistics,
    statistics_during_period,
    wait_recording_done,
)
from tests.typing import WebSocketGenerator

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
KW_SENSOR_ATTRIBUTES = {
    "state_class": "measurement",
    "unit_of_measurement": "kW",
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
    (
        "device_class",
        "state_unit",
        "display_unit",
        "statistics_unit",
        "unit_class",
        "mean",
        "min",
        "max",
    ),
    [
        (None, "%", "%", "%", "unitless", 13.050847, -10, 30),
        ("battery", "%", "%", "%", "unitless", 13.050847, -10, 30),
        ("battery", None, None, None, "unitless", 13.050847, -10, 30),
        ("distance", "m", "m", "m", "distance", 13.050847, -10, 30),
        ("distance", "mi", "mi", "mi", "distance", 13.050847, -10, 30),
        ("humidity", "%", "%", "%", "unitless", 13.050847, -10, 30),
        ("humidity", None, None, None, "unitless", 13.050847, -10, 30),
        ("pressure", "Pa", "Pa", "Pa", "pressure", 13.050847, -10, 30),
        ("pressure", "hPa", "hPa", "hPa", "pressure", 13.050847, -10, 30),
        ("pressure", "mbar", "mbar", "mbar", "pressure", 13.050847, -10, 30),
        ("pressure", "inHg", "inHg", "inHg", "pressure", 13.050847, -10, 30),
        ("pressure", "psi", "psi", "psi", "pressure", 13.050847, -10, 30),
        ("speed", "m/s", "m/s", "m/s", "speed", 13.050847, -10, 30),
        ("speed", "mph", "mph", "mph", "speed", 13.050847, -10, 30),
        ("temperature", "°C", "°C", "°C", "temperature", 13.050847, -10, 30),
        ("temperature", "°F", "°F", "°F", "temperature", 13.050847, -10, 30),
        ("volume", "m³", "m³", "m³", "volume", 13.050847, -10, 30),
        ("volume", "ft³", "ft³", "ft³", "volume", 13.050847, -10, 30),
        ("weight", "g", "g", "g", "mass", 13.050847, -10, 30),
        ("weight", "oz", "oz", "oz", "mass", 13.050847, -10, 30),
    ],
)
def test_compile_hourly_statistics(
    hass_recorder: Callable[..., HomeAssistant],
    caplog: pytest.LogCaptureFixture,
    device_class,
    state_unit,
    display_unit,
    statistics_unit,
    unit_class,
    mean,
    min,
    max,
) -> None:
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
    with freeze_time(zero) as freezer:
        four, states = record_states(hass, freezer, zero, "sensor.test1", attributes)
    hist = history.get_significant_states(
        hass, zero, four, hass.states.async_entity_ids()
    )
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)

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
            "unit_class": unit_class,
        }
    ]
    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {
        "sensor.test1": [
            {
                "start": process_timestamp(zero).timestamp(),
                "end": process_timestamp(zero + timedelta(minutes=5)).timestamp(),
                "mean": pytest.approx(mean),
                "min": pytest.approx(min),
                "max": pytest.approx(max),
                "last_reset": None,
                "state": None,
                "sum": None,
            }
        ]
    }
    assert "Error while processing event StatisticsTask" not in caplog.text


@pytest.mark.parametrize(
    (
        "device_class",
        "state_unit",
        "display_unit",
        "statistics_unit",
        "unit_class",
        "mean",
        "min",
        "max",
    ),
    [
        ("temperature", "°C", "°C", "°C", "temperature", 27.796610169491526, -10, 60),
        ("temperature", "°F", "°F", "°F", "temperature", 27.796610169491526, -10, 60),
    ],
)
def test_compile_hourly_statistics_with_some_same_last_updated(
    hass_recorder: Callable[..., HomeAssistant],
    caplog: pytest.LogCaptureFixture,
    device_class,
    state_unit,
    display_unit,
    statistics_unit,
    unit_class,
    mean,
    min,
    max,
) -> None:
    """Test compiling hourly statistics with the some of the same last updated value.

    If the last updated value is the same we will have a zero duration.
    """
    zero = dt_util.utcnow()
    hass = hass_recorder()
    setup_component(hass, "sensor", {})
    wait_recording_done(hass)  # Wait for the sensor recorder platform to be added
    entity_id = "sensor.test1"
    attributes = {
        "device_class": device_class,
        "state_class": "measurement",
        "unit_of_measurement": state_unit,
    }
    attributes = dict(attributes)
    seq = [-10, 15, 30, 60]

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
    with freeze_time(one) as freezer:
        states[entity_id].append(
            set_state(entity_id, str(seq[0]), attributes=attributes)
        )

        # Record two states at the exact same time
        freezer.move_to(two)
        states[entity_id].append(
            set_state(entity_id, str(seq[1]), attributes=attributes)
        )
        states[entity_id].append(
            set_state(entity_id, str(seq[2]), attributes=attributes)
        )

        freezer.move_to(three)
        states[entity_id].append(
            set_state(entity_id, str(seq[3]), attributes=attributes)
        )

    hist = history.get_significant_states(
        hass, zero, four, hass.states.async_entity_ids()
    )
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)

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
            "unit_class": unit_class,
        }
    ]
    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {
        "sensor.test1": [
            {
                "start": process_timestamp(zero).timestamp(),
                "end": process_timestamp(zero + timedelta(minutes=5)).timestamp(),
                "mean": pytest.approx(mean),
                "min": pytest.approx(min),
                "max": pytest.approx(max),
                "last_reset": None,
                "state": None,
                "sum": None,
            }
        ]
    }
    assert "Error while processing event StatisticsTask" not in caplog.text


@pytest.mark.parametrize(
    (
        "device_class",
        "state_unit",
        "display_unit",
        "statistics_unit",
        "unit_class",
        "mean",
        "min",
        "max",
    ),
    [
        ("temperature", "°C", "°C", "°C", "temperature", 60, -10, 60),
        ("temperature", "°F", "°F", "°F", "temperature", 60, -10, 60),
    ],
)
def test_compile_hourly_statistics_with_all_same_last_updated(
    hass_recorder: Callable[..., HomeAssistant],
    caplog: pytest.LogCaptureFixture,
    device_class,
    state_unit,
    display_unit,
    statistics_unit,
    unit_class,
    mean,
    min,
    max,
) -> None:
    """Test compiling hourly statistics with the all of the same last updated value.

    If the last updated value is the same we will have a zero duration.
    """
    zero = dt_util.utcnow()
    hass = hass_recorder()
    setup_component(hass, "sensor", {})
    wait_recording_done(hass)  # Wait for the sensor recorder platform to be added
    entity_id = "sensor.test1"
    attributes = {
        "device_class": device_class,
        "state_class": "measurement",
        "unit_of_measurement": state_unit,
    }
    attributes = dict(attributes)
    seq = [-10, 15, 30, 60]

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
    with freeze_time(two):
        states[entity_id].append(
            set_state(entity_id, str(seq[0]), attributes=attributes)
        )
        states[entity_id].append(
            set_state(entity_id, str(seq[1]), attributes=attributes)
        )
        states[entity_id].append(
            set_state(entity_id, str(seq[2]), attributes=attributes)
        )
        states[entity_id].append(
            set_state(entity_id, str(seq[3]), attributes=attributes)
        )

    hist = history.get_significant_states(
        hass, zero, four, hass.states.async_entity_ids()
    )
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)

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
            "unit_class": unit_class,
        }
    ]
    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {
        "sensor.test1": [
            {
                "start": process_timestamp(zero).timestamp(),
                "end": process_timestamp(zero + timedelta(minutes=5)).timestamp(),
                "mean": pytest.approx(mean),
                "min": pytest.approx(min),
                "max": pytest.approx(max),
                "last_reset": None,
                "state": None,
                "sum": None,
            }
        ]
    }
    assert "Error while processing event StatisticsTask" not in caplog.text


@pytest.mark.parametrize(
    (
        "device_class",
        "state_unit",
        "display_unit",
        "statistics_unit",
        "unit_class",
        "mean",
        "min",
        "max",
    ),
    [
        ("temperature", "°C", "°C", "°C", "temperature", 0, 60, 60),
        ("temperature", "°F", "°F", "°F", "temperature", 0, 60, 60),
    ],
)
def test_compile_hourly_statistics_only_state_is_and_end_of_period(
    hass_recorder: Callable[..., HomeAssistant],
    caplog: pytest.LogCaptureFixture,
    device_class,
    state_unit,
    display_unit,
    statistics_unit,
    unit_class,
    mean,
    min,
    max,
) -> None:
    """Test compiling hourly statistics when the only state at end of period."""
    zero = dt_util.utcnow()
    hass = hass_recorder()
    setup_component(hass, "sensor", {})
    wait_recording_done(hass)  # Wait for the sensor recorder platform to be added
    entity_id = "sensor.test1"
    attributes = {
        "device_class": device_class,
        "state_class": "measurement",
        "unit_of_measurement": state_unit,
    }
    attributes = dict(attributes)
    seq = [-10, 15, 30, 60]

    def set_state(entity_id, state, **kwargs):
        """Set the state."""
        hass.states.set(entity_id, state, **kwargs)
        wait_recording_done(hass)
        return hass.states.get(entity_id)

    one = zero + timedelta(seconds=1 * 5)
    two = one + timedelta(seconds=10 * 5)
    three = two + timedelta(seconds=40 * 5)
    four = three + timedelta(seconds=10 * 5)
    end = zero + timedelta(minutes=5)

    states = {entity_id: []}
    with freeze_time(end):
        states[entity_id].append(
            set_state(entity_id, str(seq[0]), attributes=attributes)
        )
        states[entity_id].append(
            set_state(entity_id, str(seq[1]), attributes=attributes)
        )
        states[entity_id].append(
            set_state(entity_id, str(seq[2]), attributes=attributes)
        )
        states[entity_id].append(
            set_state(entity_id, str(seq[3]), attributes=attributes)
        )

    hist = history.get_significant_states(
        hass, zero, four, hass.states.async_entity_ids()
    )
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)

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
            "unit_class": unit_class,
        }
    ]
    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {
        "sensor.test1": [
            {
                "start": process_timestamp(zero).timestamp(),
                "end": process_timestamp(zero + timedelta(minutes=5)).timestamp(),
                "mean": pytest.approx(mean),
                "min": pytest.approx(min),
                "max": pytest.approx(max),
                "last_reset": None,
                "state": None,
                "sum": None,
            }
        ]
    }
    assert "Error while processing event StatisticsTask" not in caplog.text


@pytest.mark.parametrize(
    ("device_class", "state_unit", "display_unit", "statistics_unit", "unit_class"),
    [
        (None, "%", "%", "%", "unitless"),
    ],
)
def test_compile_hourly_statistics_purged_state_changes(
    hass_recorder: Callable[..., HomeAssistant],
    caplog: pytest.LogCaptureFixture,
    device_class,
    state_unit,
    display_unit,
    statistics_unit,
    unit_class,
) -> None:
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
    with freeze_time(zero) as freezer:
        four, states = record_states(hass, freezer, zero, "sensor.test1", attributes)
    hist = history.get_significant_states(
        hass, zero, four, hass.states.async_entity_ids()
    )
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)

    mean = min = max = float(hist["sensor.test1"][-1].state)

    # Purge all states from the database
    with freeze_time(four):
        hass.services.call("recorder", "purge", {"keep_days": 0})
        hass.block_till_done()
        wait_recording_done(hass)
    hist = history.get_significant_states(
        hass, zero, four, hass.states.async_entity_ids()
    )
    assert not hist

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
            "unit_class": unit_class,
        }
    ]
    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {
        "sensor.test1": [
            {
                "start": process_timestamp(zero).timestamp(),
                "end": process_timestamp(zero + timedelta(minutes=5)).timestamp(),
                "mean": pytest.approx(mean),
                "min": pytest.approx(min),
                "max": pytest.approx(max),
                "last_reset": None,
                "state": None,
                "sum": None,
            }
        ]
    }
    assert "Error while processing event StatisticsTask" not in caplog.text


@pytest.mark.parametrize("attributes", [TEMPERATURE_SENSOR_ATTRIBUTES])
def test_compile_hourly_statistics_wrong_unit(
    hass_recorder: Callable[..., HomeAssistant],
    caplog: pytest.LogCaptureFixture,
    attributes,
) -> None:
    """Test compiling hourly statistics for sensor with unit not matching device class."""
    zero = dt_util.utcnow()
    hass = hass_recorder()
    setup_component(hass, "sensor", {})
    wait_recording_done(hass)  # Wait for the sensor recorder platform to be added
    with freeze_time(zero) as freezer:
        four, states = record_states(hass, freezer, zero, "sensor.test1", attributes)

        attributes_tmp = dict(attributes)
        attributes_tmp["unit_of_measurement"] = "invalid"
        _, _states = record_states(hass, freezer, zero, "sensor.test2", attributes_tmp)
        states = {**states, **_states}
        attributes_tmp.pop("unit_of_measurement")
        _, _states = record_states(hass, freezer, zero, "sensor.test3", attributes_tmp)
        states = {**states, **_states}

        attributes_tmp = dict(attributes)
        attributes_tmp["state_class"] = "invalid"
        _, _states = record_states(hass, freezer, zero, "sensor.test4", attributes_tmp)
        states = {**states, **_states}
        attributes_tmp.pop("state_class")
        _, _states = record_states(hass, freezer, zero, "sensor.test5", attributes_tmp)
        states = {**states, **_states}

        attributes_tmp = dict(attributes)
        attributes_tmp["device_class"] = "invalid"
        _, _states = record_states(hass, freezer, zero, "sensor.test6", attributes_tmp)
        states = {**states, **_states}
        attributes_tmp.pop("device_class")
        _, _states = record_states(hass, freezer, zero, "sensor.test7", attributes_tmp)
        states = {**states, **_states}

    hist = history.get_significant_states(
        hass, zero, four, hass.states.async_entity_ids()
    )
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)

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
            "unit_class": "temperature",
        },
        {
            "display_unit_of_measurement": "invalid",
            "has_mean": True,
            "has_sum": False,
            "name": None,
            "source": "recorder",
            "statistic_id": "sensor.test2",
            "statistics_unit_of_measurement": "invalid",
            "unit_class": None,
        },
        {
            "display_unit_of_measurement": None,
            "has_mean": True,
            "has_sum": False,
            "name": None,
            "source": "recorder",
            "statistic_id": "sensor.test3",
            "statistics_unit_of_measurement": None,
            "unit_class": "unitless",
        },
        {
            "statistic_id": "sensor.test6",
            "display_unit_of_measurement": "°C",
            "has_mean": True,
            "has_sum": False,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": "°C",
            "unit_class": "temperature",
        },
        {
            "statistic_id": "sensor.test7",
            "display_unit_of_measurement": "°C",
            "has_mean": True,
            "has_sum": False,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": "°C",
            "unit_class": "temperature",
        },
    ]
    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {
        "sensor.test1": [
            {
                "start": process_timestamp(zero).timestamp(),
                "end": process_timestamp(zero + timedelta(minutes=5)).timestamp(),
                "mean": pytest.approx(13.050847),
                "min": pytest.approx(-10.0),
                "max": pytest.approx(30.0),
                "last_reset": None,
                "state": None,
                "sum": None,
            }
        ],
        "sensor.test2": [
            {
                "start": process_timestamp(zero).timestamp(),
                "end": process_timestamp(zero + timedelta(minutes=5)).timestamp(),
                "mean": 13.05084745762712,
                "min": -10.0,
                "max": 30.0,
                "last_reset": None,
                "state": None,
                "sum": None,
            }
        ],
        "sensor.test3": [
            {
                "start": process_timestamp(zero).timestamp(),
                "end": process_timestamp(zero + timedelta(minutes=5)).timestamp(),
                "mean": 13.05084745762712,
                "min": -10.0,
                "max": 30.0,
                "last_reset": None,
                "state": None,
                "sum": None,
            }
        ],
        "sensor.test6": [
            {
                "start": process_timestamp(zero).timestamp(),
                "end": process_timestamp(zero + timedelta(minutes=5)).timestamp(),
                "mean": pytest.approx(13.050847),
                "min": pytest.approx(-10.0),
                "max": pytest.approx(30.0),
                "last_reset": None,
                "state": None,
                "sum": None,
            }
        ],
        "sensor.test7": [
            {
                "start": process_timestamp(zero).timestamp(),
                "end": process_timestamp(zero + timedelta(minutes=5)).timestamp(),
                "mean": pytest.approx(13.050847),
                "min": pytest.approx(-10.0),
                "max": pytest.approx(30.0),
                "last_reset": None,
                "state": None,
                "sum": None,
            }
        ],
    }
    assert "Error while processing event StatisticsTask" not in caplog.text


@pytest.mark.parametrize("state_class", ["total"])
@pytest.mark.parametrize(
    (
        "units",
        "device_class",
        "state_unit",
        "display_unit",
        "statistics_unit",
        "unit_class",
        "factor",
    ),
    [
        (US_CUSTOMARY_SYSTEM, "distance", "m", "m", "m", "distance", 1),
        (US_CUSTOMARY_SYSTEM, "distance", "mi", "mi", "mi", "distance", 1),
        (US_CUSTOMARY_SYSTEM, "energy", "kWh", "kWh", "kWh", "energy", 1),
        (US_CUSTOMARY_SYSTEM, "energy", "Wh", "Wh", "Wh", "energy", 1),
        (US_CUSTOMARY_SYSTEM, "gas", "m³", "m³", "m³", "volume", 1),
        (US_CUSTOMARY_SYSTEM, "gas", "ft³", "ft³", "ft³", "volume", 1),
        (US_CUSTOMARY_SYSTEM, "monetary", "EUR", "EUR", "EUR", None, 1),
        (US_CUSTOMARY_SYSTEM, "monetary", "SEK", "SEK", "SEK", None, 1),
        (US_CUSTOMARY_SYSTEM, "volume", "m³", "m³", "m³", "volume", 1),
        (US_CUSTOMARY_SYSTEM, "volume", "ft³", "ft³", "ft³", "volume", 1),
        (US_CUSTOMARY_SYSTEM, "weight", "g", "g", "g", "mass", 1),
        (US_CUSTOMARY_SYSTEM, "weight", "oz", "oz", "oz", "mass", 1),
        (METRIC_SYSTEM, "distance", "m", "m", "m", "distance", 1),
        (METRIC_SYSTEM, "distance", "mi", "mi", "mi", "distance", 1),
        (METRIC_SYSTEM, "energy", "kWh", "kWh", "kWh", "energy", 1),
        (METRIC_SYSTEM, "energy", "Wh", "Wh", "Wh", "energy", 1),
        (METRIC_SYSTEM, "gas", "m³", "m³", "m³", "volume", 1),
        (METRIC_SYSTEM, "gas", "ft³", "ft³", "ft³", "volume", 1),
        (METRIC_SYSTEM, "monetary", "EUR", "EUR", "EUR", None, 1),
        (METRIC_SYSTEM, "monetary", "SEK", "SEK", "SEK", None, 1),
        (METRIC_SYSTEM, "volume", "m³", "m³", "m³", "volume", 1),
        (METRIC_SYSTEM, "volume", "ft³", "ft³", "ft³", "volume", 1),
        (METRIC_SYSTEM, "weight", "g", "g", "g", "mass", 1),
        (METRIC_SYSTEM, "weight", "oz", "oz", "oz", "mass", 1),
    ],
)
async def test_compile_hourly_sum_statistics_amount(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
    units,
    state_class,
    device_class,
    state_unit,
    display_unit,
    statistics_unit,
    unit_class,
    factor,
) -> None:
    """Test compiling hourly statistics."""
    period0 = dt_util.utcnow()
    period0_end = period1 = period0 + timedelta(minutes=5)
    period1_end = period2 = period0 + timedelta(minutes=10)
    period2_end = period0 + timedelta(minutes=15)
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
    with freeze_time(period0) as freezer:
        four, eight, states = await hass.async_add_executor_job(
            record_meter_states, hass, freezer, period0, "sensor.test1", attributes, seq
        )
    await async_wait_recording_done(hass)
    hist = history.get_significant_states(
        hass,
        period0 - timedelta.resolution,
        eight + timedelta.resolution,
        hass.states.async_entity_ids(),
    )
    assert_multiple_states_equal_without_context_and_last_changed(
        dict(states)["sensor.test1"], dict(hist)["sensor.test1"]
    )

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
            "display_unit_of_measurement": statistics_unit,
            "has_mean": False,
            "has_sum": True,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": statistics_unit,
            "unit_class": unit_class,
        }
    ]
    stats = statistics_during_period(hass, period0, period="5minute")
    expected_stats = {
        "sensor.test1": [
            {
                "start": process_timestamp(period0).timestamp(),
                "end": process_timestamp(period0_end).timestamp(),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": process_timestamp(period0).timestamp(),
                "state": pytest.approx(factor * seq[2]),
                "sum": pytest.approx(factor * 10.0),
            },
            {
                "start": process_timestamp(period1).timestamp(),
                "end": process_timestamp(period1_end).timestamp(),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": process_timestamp(four).timestamp(),
                "state": pytest.approx(factor * seq[5]),
                "sum": pytest.approx(factor * 40.0),
            },
            {
                "start": process_timestamp(period2).timestamp(),
                "end": process_timestamp(period2_end).timestamp(),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": process_timestamp(four).timestamp(),
                "state": pytest.approx(factor * seq[8]),
                "sum": pytest.approx(factor * 70.0),
            },
        ]
    }
    assert stats == expected_stats

    # With an offset of 1 minute, we expect to get the 2nd and 3rd periods
    stats = statistics_during_period(
        hass, period0 + timedelta(minutes=1), period="5minute"
    )
    assert stats == {"sensor.test1": expected_stats["sensor.test1"][1:3]}

    # With an offset of 5 minutes, we expect to get the 2nd and 3rd periods
    stats = statistics_during_period(
        hass, period0 + timedelta(minutes=5), period="5minute"
    )
    assert stats == {"sensor.test1": expected_stats["sensor.test1"][1:3]}

    # With an offset of 6 minutes, we expect to get the 3rd period
    stats = statistics_during_period(
        hass, period0 + timedelta(minutes=6), period="5minute"
    )
    assert stats == {"sensor.test1": expected_stats["sensor.test1"][2:3]}

    assert "Error while processing event StatisticsTask" not in caplog.text
    assert "Detected new cycle for sensor.test1, last_reset set to" in caplog.text
    assert "Compiling initial sum statistics for sensor.test1" in caplog.text
    assert "Detected new cycle for sensor.test1, value dropped" not in caplog.text

    client = await hass_ws_client()

    # Adjust the inserted statistics
    await client.send_json(
        {
            "id": 1,
            "type": "recorder/adjust_sum_statistics",
            "statistic_id": "sensor.test1",
            "start_time": period1.isoformat(),
            "adjustment": 100.0,
            "adjustment_unit_of_measurement": display_unit,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    await async_wait_recording_done(hass)

    expected_stats["sensor.test1"][1]["sum"] = pytest.approx(factor * 40.0 + 100)
    expected_stats["sensor.test1"][2]["sum"] = pytest.approx(factor * 70.0 + 100)
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
            "adjustment_unit_of_measurement": display_unit,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    await async_wait_recording_done(hass)

    expected_stats["sensor.test1"][1]["sum"] = pytest.approx(factor * 40.0 + 100)
    expected_stats["sensor.test1"][2]["sum"] = pytest.approx(factor * 70.0 - 300)
    stats = statistics_during_period(hass, period0, period="5minute")
    assert stats == expected_stats


@pytest.mark.parametrize("state_class", ["total"])
@pytest.mark.parametrize(
    (
        "device_class",
        "state_unit",
        "display_unit",
        "statistics_unit",
        "unit_class",
        "factor",
    ),
    [
        ("energy", "kWh", "kWh", "kWh", "energy", 1),
        ("energy", "Wh", "Wh", "Wh", "energy", 1),
        ("monetary", "EUR", "EUR", "EUR", None, 1),
        ("monetary", "SEK", "SEK", "SEK", None, 1),
        ("gas", "m³", "m³", "m³", "volume", 1),
        ("gas", "ft³", "ft³", "ft³", "volume", 1),
    ],
)
def test_compile_hourly_sum_statistics_amount_reset_every_state_change(
    hass_recorder: Callable[..., HomeAssistant],
    caplog: pytest.LogCaptureFixture,
    state_class,
    device_class,
    state_unit,
    display_unit,
    statistics_unit,
    unit_class,
    factor,
) -> None:
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
    with freeze_time(zero) as freezer:
        # Insert states for a 1st statistics period
        one = zero
        for i in range(len(seq)):
            one = one + timedelta(seconds=5)
            attributes = dict(attributes)
            attributes["last_reset"] = dt_util.as_local(one).isoformat()
            _states = record_meter_state(
                hass, freezer, one, "sensor.test1", attributes, seq[i : i + 1]
            )
            states["sensor.test1"].extend(_states["sensor.test1"])

        # Insert states for a 2nd statistics period
        two = zero + timedelta(minutes=5)
        for i in range(len(seq)):
            two = two + timedelta(seconds=5)
            attributes = dict(attributes)
            attributes["last_reset"] = dt_util.as_local(two).isoformat()
            _states = record_meter_state(
                hass, freezer, two, "sensor.test1", attributes, seq[i : i + 1]
            )
            states["sensor.test1"].extend(_states["sensor.test1"])

    hist = history.get_significant_states(
        hass,
        zero - timedelta.resolution,
        two + timedelta.resolution,
        hass.states.async_entity_ids(),
        significant_changes_only=False,
    )
    assert_multiple_states_equal_without_context_and_last_changed(
        dict(states)["sensor.test1"], dict(hist)["sensor.test1"]
    )

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
            "unit_class": unit_class,
        }
    ]
    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {
        "sensor.test1": [
            {
                "start": process_timestamp(zero).timestamp(),
                "end": process_timestamp(zero + timedelta(minutes=5)).timestamp(),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": process_timestamp(dt_util.as_local(one)).timestamp(),
                "state": pytest.approx(factor * seq[7]),
                "sum": pytest.approx(factor * (sum(seq) - seq[0])),
            },
            {
                "start": process_timestamp(zero + timedelta(minutes=5)).timestamp(),
                "end": process_timestamp(zero + timedelta(minutes=10)).timestamp(),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": process_timestamp(dt_util.as_local(two)).timestamp(),
                "state": pytest.approx(factor * seq[7]),
                "sum": pytest.approx(factor * (2 * sum(seq) - seq[0])),
            },
        ]
    }
    assert "Error while processing event StatisticsTask" not in caplog.text


@pytest.mark.parametrize("state_class", ["total"])
@pytest.mark.parametrize(
    (
        "device_class",
        "state_unit",
        "display_unit",
        "statistics_unit",
        "unit_class",
        "factor",
    ),
    [
        ("energy", "kWh", "kWh", "kWh", "energy", 1),
    ],
)
def test_compile_hourly_sum_statistics_amount_invalid_last_reset(
    hass_recorder: Callable[..., HomeAssistant],
    caplog: pytest.LogCaptureFixture,
    state_class,
    device_class,
    state_unit,
    display_unit,
    statistics_unit,
    unit_class,
    factor,
) -> None:
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
    with freeze_time(zero) as freezer:
        one = zero
        for i in range(len(seq)):
            one = one + timedelta(seconds=5)
            attributes = dict(attributes)
            attributes["last_reset"] = dt_util.as_local(one).isoformat()
            if i == 3:
                attributes["last_reset"] = "festivus"  # not a valid time
            _states = record_meter_state(
                hass, freezer, one, "sensor.test1", attributes, seq[i : i + 1]
            )
            states["sensor.test1"].extend(_states["sensor.test1"])

    hist = history.get_significant_states(
        hass,
        zero - timedelta.resolution,
        one + timedelta.resolution,
        hass.states.async_entity_ids(),
        significant_changes_only=False,
    )
    assert_multiple_states_equal_without_context_and_last_changed(
        dict(states)["sensor.test1"], dict(hist)["sensor.test1"]
    )

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
            "unit_class": unit_class,
        }
    ]
    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {
        "sensor.test1": [
            {
                "start": process_timestamp(zero).timestamp(),
                "end": process_timestamp(zero + timedelta(minutes=5)).timestamp(),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": process_timestamp(dt_util.as_local(one)).timestamp(),
                "state": pytest.approx(factor * seq[7]),
                "sum": pytest.approx(factor * (sum(seq) - seq[0] - seq[3])),
            },
        ]
    }
    assert "Error while processing event StatisticsTask" not in caplog.text
    assert "Ignoring invalid last reset 'festivus' for sensor.test1" in caplog.text


@pytest.mark.parametrize("state_class", ["total"])
@pytest.mark.parametrize(
    (
        "device_class",
        "state_unit",
        "display_unit",
        "statistics_unit",
        "unit_class",
        "factor",
    ),
    [
        ("energy", "kWh", "kWh", "kWh", "energy", 1),
    ],
)
def test_compile_hourly_sum_statistics_nan_inf_state(
    hass_recorder: Callable[..., HomeAssistant],
    caplog: pytest.LogCaptureFixture,
    state_class,
    device_class,
    state_unit,
    display_unit,
    statistics_unit,
    unit_class,
    factor,
) -> None:
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
    with freeze_time(zero) as freezer:
        one = zero
        for i in range(len(seq)):
            one = one + timedelta(seconds=5)
            attributes = dict(attributes)
            attributes["last_reset"] = dt_util.as_local(one).isoformat()
            _states = record_meter_state(
                hass, freezer, one, "sensor.test1", attributes, seq[i : i + 1]
            )
            states["sensor.test1"].extend(_states["sensor.test1"])

    hist = history.get_significant_states(
        hass,
        zero - timedelta.resolution,
        one + timedelta.resolution,
        hass.states.async_entity_ids(),
        significant_changes_only=False,
    )
    assert_multiple_states_equal_without_context_and_last_changed(
        dict(states)["sensor.test1"], dict(hist)["sensor.test1"]
    )

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
            "unit_class": unit_class,
        }
    ]
    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {
        "sensor.test1": [
            {
                "start": process_timestamp(zero).timestamp(),
                "end": process_timestamp(zero + timedelta(minutes=5)).timestamp(),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": process_timestamp(one).timestamp(),
                "state": pytest.approx(factor * seq[7]),
                "sum": pytest.approx(
                    factor * (seq[2] + seq[3] + seq[4] + seq[6] + seq[7])
                ),
            },
        ]
    }
    assert "Error while processing event StatisticsTask" not in caplog.text


@pytest.mark.parametrize(
    (
        "entity_id",
        "device_class",
        "state_unit",
        "display_unit",
        "statistics_unit",
        "unit_class",
        "offset",
        "warning_1",
        "warning_2",
    ),
    [
        (
            "sensor.test1",
            "energy",
            "kWh",
            "kWh",
            "kWh",
            "energy",
            0,
            "",
            "bug report at https://github.com/home-assistant/core/issues?q=is%3Aopen+is%3Aissue",
        ),
        (
            "sensor.power_consumption",
            "power",
            "W",
            "W",
            "W",
            "power",
            15,
            "from integration demo ",
            "bug report at https://github.com/home-assistant/core/issues?q=is%3Aopen+is%3Aissue+label%3A%22integration%3A+demo%22",
        ),
        (
            "sensor.custom_sensor",
            "energy",
            "kWh",
            "kWh",
            "kWh",
            "energy",
            0,
            "from integration test ",
            "report it to the custom integration author",
        ),
    ],
)
@pytest.mark.parametrize("state_class", ["total_increasing"])
def test_compile_hourly_sum_statistics_negative_state(
    hass_recorder: Callable[..., HomeAssistant],
    caplog: pytest.LogCaptureFixture,
    entity_id,
    warning_1,
    warning_2,
    state_class,
    device_class,
    state_unit,
    display_unit,
    statistics_unit,
    unit_class,
    offset,
) -> None:
    """Test compiling hourly statistics with negative states."""
    zero = dt_util.utcnow()
    hass = hass_recorder()
    hass.data.pop(loader.DATA_CUSTOM_COMPONENTS)

    platform = getattr(hass.components, "test.sensor")
    platform.init(empty=True)
    mocksensor = platform.MockSensor(name="custom_sensor")
    mocksensor._attr_should_poll = False
    platform.ENTITIES["custom_sensor"] = mocksensor

    setup_component(hass, "homeassistant", {})
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
    with freeze_time(zero) as freezer:
        for i in range(len(seq)):
            one = one + timedelta(seconds=5)
            _states = record_meter_state(
                hass, freezer, one, entity_id, attributes, seq[i : i + 1]
            )
            states[entity_id].extend(_states[entity_id])

    hist = history.get_significant_states(
        hass,
        zero - timedelta.resolution,
        one + timedelta.resolution,
        hass.states.async_entity_ids(),
        significant_changes_only=False,
    )
    assert_multiple_states_equal_without_context_and_last_changed(
        dict(states)[entity_id], dict(hist)[entity_id]
    )

    do_adhoc_statistics(hass, start=zero)
    wait_recording_done(hass)
    statistic_ids = list_statistic_ids(hass)
    assert {
        "display_unit_of_measurement": display_unit,
        "has_mean": False,
        "has_sum": True,
        "name": None,
        "source": "recorder",
        "statistic_id": entity_id,
        "statistics_unit_of_measurement": statistics_unit,
        "unit_class": unit_class,
    } in statistic_ids
    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats[entity_id] == [
        {
            "start": process_timestamp(zero).timestamp(),
            "end": process_timestamp(zero + timedelta(minutes=5)).timestamp(),
            "max": None,
            "mean": None,
            "min": None,
            "last_reset": None,
            "state": pytest.approx(seq[7]),
            "sum": pytest.approx(offset + 15),  # (20 - 15) + (10 - 0)
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
    (
        "device_class",
        "state_unit",
        "display_unit",
        "statistics_unit",
        "unit_class",
        "factor",
    ),
    [
        ("energy", "kWh", "kWh", "kWh", "energy", 1),
        ("energy", "Wh", "Wh", "Wh", "energy", 1),
        ("monetary", "EUR", "EUR", "EUR", None, 1),
        ("monetary", "SEK", "SEK", "SEK", None, 1),
        ("gas", "m³", "m³", "m³", "volume", 1),
        ("gas", "ft³", "ft³", "ft³", "volume", 1),
    ],
)
def test_compile_hourly_sum_statistics_total_no_reset(
    hass_recorder: Callable[..., HomeAssistant],
    caplog: pytest.LogCaptureFixture,
    device_class,
    state_unit,
    display_unit,
    statistics_unit,
    unit_class,
    factor,
) -> None:
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
    with freeze_time(period0) as freezer:
        four, eight, states = record_meter_states(
            hass, freezer, period0, "sensor.test1", attributes, seq
        )
    wait_recording_done(hass)
    hist = history.get_significant_states(
        hass,
        period0 - timedelta.resolution,
        eight + timedelta.resolution,
        hass.states.async_entity_ids(),
    )
    assert_multiple_states_equal_without_context_and_last_changed(
        dict(states)["sensor.test1"], dict(hist)["sensor.test1"]
    )

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
            "unit_class": unit_class,
        }
    ]
    stats = statistics_during_period(hass, period0, period="5minute")
    assert stats == {
        "sensor.test1": [
            {
                "start": process_timestamp(period0).timestamp(),
                "end": process_timestamp(period0_end).timestamp(),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": None,
                "state": pytest.approx(factor * seq[2]),
                "sum": pytest.approx(factor * 10.0),
            },
            {
                "start": process_timestamp(period1).timestamp(),
                "end": process_timestamp(period1_end).timestamp(),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": None,
                "state": pytest.approx(factor * seq[5]),
                "sum": pytest.approx(factor * 30.0),
            },
            {
                "start": process_timestamp(period2).timestamp(),
                "end": process_timestamp(period2_end).timestamp(),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": None,
                "state": pytest.approx(factor * seq[8]),
                "sum": pytest.approx(factor * 60.0),
            },
        ]
    }
    assert "Error while processing event StatisticsTask" not in caplog.text


@pytest.mark.parametrize(
    (
        "device_class",
        "state_unit",
        "display_unit",
        "statistics_unit",
        "unit_class",
        "factor",
    ),
    [
        ("energy", "kWh", "kWh", "kWh", "energy", 1),
        ("energy", "Wh", "Wh", "Wh", "energy", 1),
        ("gas", "m³", "m³", "m³", "volume", 1),
        ("gas", "ft³", "ft³", "ft³", "volume", 1),
    ],
)
def test_compile_hourly_sum_statistics_total_increasing(
    hass_recorder: Callable[..., HomeAssistant],
    caplog: pytest.LogCaptureFixture,
    device_class,
    state_unit,
    display_unit,
    statistics_unit,
    unit_class,
    factor,
) -> None:
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
    with freeze_time(period0) as freezer:
        four, eight, states = record_meter_states(
            hass, freezer, period0, "sensor.test1", attributes, seq
        )
    wait_recording_done(hass)
    hist = history.get_significant_states(
        hass,
        period0 - timedelta.resolution,
        eight + timedelta.resolution,
        hass.states.async_entity_ids(),
    )
    assert_multiple_states_equal_without_context_and_last_changed(
        dict(states)["sensor.test1"], dict(hist)["sensor.test1"]
    )

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
            "unit_class": unit_class,
        }
    ]
    stats = statistics_during_period(hass, period0, period="5minute")
    assert stats == {
        "sensor.test1": [
            {
                "start": process_timestamp(period0).timestamp(),
                "end": process_timestamp(period0_end).timestamp(),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": None,
                "state": pytest.approx(factor * seq[2]),
                "sum": pytest.approx(factor * 10.0),
            },
            {
                "start": process_timestamp(period1).timestamp(),
                "end": process_timestamp(period1_end).timestamp(),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": None,
                "state": pytest.approx(factor * seq[5]),
                "sum": pytest.approx(factor * 50.0),
            },
            {
                "start": process_timestamp(period2).timestamp(),
                "end": process_timestamp(period2_end).timestamp(),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": None,
                "state": pytest.approx(factor * seq[8]),
                "sum": pytest.approx(factor * 80.0),
            },
        ]
    }
    assert "Error while processing event StatisticsTask" not in caplog.text
    assert "Detected new cycle for sensor.test1, last_reset set to" not in caplog.text
    assert "Compiling initial sum statistics for sensor.test1" in caplog.text
    assert "Detected new cycle for sensor.test1, value dropped" in caplog.text


@pytest.mark.parametrize(
    (
        "device_class",
        "state_unit",
        "display_unit",
        "statistics_unit",
        "unit_class",
        "factor",
    ),
    [("energy", "kWh", "kWh", "kWh", "energy", 1)],
)
def test_compile_hourly_sum_statistics_total_increasing_small_dip(
    hass_recorder: Callable[..., HomeAssistant],
    caplog: pytest.LogCaptureFixture,
    device_class,
    state_unit,
    display_unit,
    statistics_unit,
    unit_class,
    factor,
) -> None:
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
    with freeze_time(period0) as freezer:
        four, eight, states = record_meter_states(
            hass, freezer, period0, "sensor.test1", attributes, seq
        )
    wait_recording_done(hass)
    hist = history.get_significant_states(
        hass,
        period0 - timedelta.resolution,
        eight + timedelta.resolution,
        hass.states.async_entity_ids(),
    )
    assert_multiple_states_equal_without_context_and_last_changed(
        dict(states)["sensor.test1"], dict(hist)["sensor.test1"]
    )

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
            "unit_class": unit_class,
        }
    ]
    stats = statistics_during_period(hass, period0, period="5minute")
    assert stats == {
        "sensor.test1": [
            {
                "last_reset": None,
                "start": process_timestamp(period0).timestamp(),
                "end": process_timestamp(period0_end).timestamp(),
                "max": None,
                "mean": None,
                "min": None,
                "state": pytest.approx(factor * seq[2]),
                "sum": pytest.approx(factor * 10.0),
            },
            {
                "last_reset": None,
                "start": process_timestamp(period1).timestamp(),
                "end": process_timestamp(period1_end).timestamp(),
                "max": None,
                "mean": None,
                "min": None,
                "state": pytest.approx(factor * seq[5]),
                "sum": pytest.approx(factor * 30.0),
            },
            {
                "last_reset": None,
                "start": process_timestamp(period2).timestamp(),
                "end": process_timestamp(period2_end).timestamp(),
                "max": None,
                "mean": None,
                "min": None,
                "state": pytest.approx(factor * seq[8]),
                "sum": pytest.approx(factor * 60.0),
            },
        ]
    }
    assert "Error while processing event StatisticsTask" not in caplog.text


def test_compile_hourly_energy_statistics_unsupported(
    hass_recorder: Callable[..., HomeAssistant], caplog: pytest.LogCaptureFixture
) -> None:
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

    with freeze_time(period0) as freezer:
        four, eight, states = record_meter_states(
            hass, freezer, period0, "sensor.test1", sns1_attr, seq1
        )
        _, _, _states = record_meter_states(
            hass, freezer, period0, "sensor.test2", sns2_attr, seq2
        )
        states = {**states, **_states}
        _, _, _states = record_meter_states(
            hass, freezer, period0, "sensor.test3", sns3_attr, seq3
        )
    states = {**states, **_states}
    wait_recording_done(hass)

    hist = history.get_significant_states(
        hass,
        period0 - timedelta.resolution,
        eight + timedelta.resolution,
        hass.states.async_entity_ids(),
    )
    assert_multiple_states_equal_without_context_and_last_changed(
        dict(states)["sensor.test1"], dict(hist)["sensor.test1"]
    )

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
            "unit_class": "energy",
        }
    ]
    stats = statistics_during_period(hass, period0, period="5minute")
    assert stats == {
        "sensor.test1": [
            {
                "start": process_timestamp(period0).timestamp(),
                "end": process_timestamp(period0_end).timestamp(),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": process_timestamp(period0).timestamp(),
                "state": pytest.approx(20.0),
                "sum": pytest.approx(10.0),
            },
            {
                "start": process_timestamp(period1).timestamp(),
                "end": process_timestamp(period1_end).timestamp(),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": process_timestamp(four).timestamp(),
                "state": pytest.approx(40.0),
                "sum": pytest.approx(40.0),
            },
            {
                "start": process_timestamp(period2).timestamp(),
                "end": process_timestamp(period2_end).timestamp(),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": process_timestamp(four).timestamp(),
                "state": pytest.approx(70.0),
                "sum": pytest.approx(70.0),
            },
        ]
    }
    assert "Error while processing event StatisticsTask" not in caplog.text


def test_compile_hourly_energy_statistics_multiple(
    hass_recorder: Callable[..., HomeAssistant], caplog: pytest.LogCaptureFixture
) -> None:
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

    with freeze_time(period0) as freezer:
        four, eight, states = record_meter_states(
            hass, freezer, period0, "sensor.test1", sns1_attr, seq1
        )
        _, _, _states = record_meter_states(
            hass, freezer, period0, "sensor.test2", sns2_attr, seq2
        )
        states = {**states, **_states}
        _, _, _states = record_meter_states(
            hass, freezer, period0, "sensor.test3", sns3_attr, seq3
        )
    states = {**states, **_states}
    wait_recording_done(hass)
    hist = history.get_significant_states(
        hass,
        period0 - timedelta.resolution,
        eight + timedelta.resolution,
        hass.states.async_entity_ids(),
    )
    assert_multiple_states_equal_without_context_and_last_changed(
        dict(states)["sensor.test1"], dict(hist)["sensor.test1"]
    )

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
            "unit_class": "energy",
        },
        {
            "statistic_id": "sensor.test2",
            "display_unit_of_measurement": "kWh",
            "has_mean": False,
            "has_sum": True,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": "kWh",
            "unit_class": "energy",
        },
        {
            "statistic_id": "sensor.test3",
            "display_unit_of_measurement": "Wh",
            "has_mean": False,
            "has_sum": True,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": "Wh",
            "unit_class": "energy",
        },
    ]
    stats = statistics_during_period(hass, period0, period="5minute")
    assert stats == {
        "sensor.test1": [
            {
                "start": process_timestamp(period0).timestamp(),
                "end": process_timestamp(period0_end).timestamp(),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": process_timestamp(period0).timestamp(),
                "state": pytest.approx(20.0),
                "sum": pytest.approx(10.0),
            },
            {
                "start": process_timestamp(period1).timestamp(),
                "end": process_timestamp(period1_end).timestamp(),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": process_timestamp(four).timestamp(),
                "state": pytest.approx(40.0),
                "sum": pytest.approx(40.0),
            },
            {
                "start": process_timestamp(period2).timestamp(),
                "end": process_timestamp(period2_end).timestamp(),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": process_timestamp(four).timestamp(),
                "state": pytest.approx(70.0),
                "sum": pytest.approx(70.0),
            },
        ],
        "sensor.test2": [
            {
                "start": process_timestamp(period0).timestamp(),
                "end": process_timestamp(period0_end).timestamp(),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": process_timestamp(period0).timestamp(),
                "state": pytest.approx(130.0),
                "sum": pytest.approx(20.0),
            },
            {
                "start": process_timestamp(period1).timestamp(),
                "end": process_timestamp(period1_end).timestamp(),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": process_timestamp(four).timestamp(),
                "state": pytest.approx(45.0),
                "sum": pytest.approx(-65.0),
            },
            {
                "start": process_timestamp(period2).timestamp(),
                "end": process_timestamp(period2_end).timestamp(),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": process_timestamp(four).timestamp(),
                "state": pytest.approx(75.0),
                "sum": pytest.approx(-35.0),
            },
        ],
        "sensor.test3": [
            {
                "start": process_timestamp(period0).timestamp(),
                "end": process_timestamp(period0_end).timestamp(),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": process_timestamp(period0).timestamp(),
                "state": pytest.approx(5.0),
                "sum": pytest.approx(5.0),
            },
            {
                "start": process_timestamp(period1).timestamp(),
                "end": process_timestamp(period1_end).timestamp(),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": process_timestamp(four).timestamp(),
                "state": pytest.approx(50.0),
                "sum": pytest.approx(60.0),
            },
            {
                "start": process_timestamp(period2).timestamp(),
                "end": process_timestamp(period2_end).timestamp(),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": process_timestamp(four).timestamp(),
                "state": pytest.approx(90.0),
                "sum": pytest.approx(100.0),
            },
        ],
    }
    assert "Error while processing event StatisticsTask" not in caplog.text


@pytest.mark.parametrize(
    ("device_class", "state_unit", "value"),
    [
        ("battery", "%", 30),
        ("battery", None, 30),
        ("distance", "m", 30),
        ("distance", "mi", 30),
        ("humidity", "%", 30),
        ("humidity", None, 30),
        ("pressure", "Pa", 30),
        ("pressure", "hPa", 30),
        ("pressure", "mbar", 30),
        ("pressure", "inHg", 30),
        ("pressure", "psi", 30),
        ("speed", "m/s", 30),
        ("speed", "mph", 30),
        ("temperature", "°C", 30),
        ("temperature", "°F", 30),
        ("volume", "m³", 30),
        ("volume", "ft³", 30),
        ("weight", "g", 30),
        ("weight", "oz", 30),
    ],
)
def test_compile_hourly_statistics_unchanged(
    hass_recorder: Callable[..., HomeAssistant],
    caplog: pytest.LogCaptureFixture,
    device_class,
    state_unit,
    value,
) -> None:
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
    with freeze_time(zero) as freezer:
        four, states = record_states(hass, freezer, zero, "sensor.test1", attributes)
    hist = history.get_significant_states(
        hass, zero, four, hass.states.async_entity_ids()
    )
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)

    do_adhoc_statistics(hass, start=four)
    wait_recording_done(hass)
    stats = statistics_during_period(hass, four, period="5minute")
    assert stats == {
        "sensor.test1": [
            {
                "start": process_timestamp(four).timestamp(),
                "end": process_timestamp(four + timedelta(minutes=5)).timestamp(),
                "mean": pytest.approx(value),
                "min": pytest.approx(value),
                "max": pytest.approx(value),
                "last_reset": None,
                "state": None,
                "sum": None,
            }
        ]
    }
    assert "Error while processing event StatisticsTask" not in caplog.text


def test_compile_hourly_statistics_partially_unavailable(
    hass_recorder: Callable[..., HomeAssistant], caplog: pytest.LogCaptureFixture
) -> None:
    """Test compiling hourly statistics, with the sensor being partially unavailable."""
    zero = dt_util.utcnow()
    hass = hass_recorder()
    setup_component(hass, "sensor", {})
    wait_recording_done(hass)  # Wait for the sensor recorder platform to be added
    four, states = record_states_partially_unavailable(
        hass, zero, "sensor.test1", TEMPERATURE_SENSOR_ATTRIBUTES
    )
    hist = history.get_significant_states(
        hass, zero, four, hass.states.async_entity_ids()
    )
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)

    do_adhoc_statistics(hass, start=zero)
    wait_recording_done(hass)
    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {
        "sensor.test1": [
            {
                "start": process_timestamp(zero).timestamp(),
                "end": process_timestamp(zero + timedelta(minutes=5)).timestamp(),
                "mean": pytest.approx(21.1864406779661),
                "min": pytest.approx(10.0),
                "max": pytest.approx(25.0),
                "last_reset": None,
                "state": None,
                "sum": None,
            }
        ]
    }
    assert "Error while processing event StatisticsTask" not in caplog.text


@pytest.mark.parametrize(
    ("device_class", "state_unit", "value"),
    [
        ("battery", "%", 30),
        ("battery", None, 30),
        ("distance", "m", 30),
        ("distance", "mi", 30),
        ("humidity", "%", 30),
        ("humidity", None, 30),
        ("pressure", "Pa", 30),
        ("pressure", "hPa", 30),
        ("pressure", "mbar", 30),
        ("pressure", "inHg", 30),
        ("pressure", "psi", 30),
        ("speed", "m/s", 30),
        ("speed", "mph", 30),
        ("temperature", "°C", 30),
        ("temperature", "°F", 30),
        ("volume", "m³", 30),
        ("volume", "ft³", 30),
        ("weight", "g", 30),
        ("weight", "oz", 30),
    ],
)
def test_compile_hourly_statistics_unavailable(
    hass_recorder: Callable[..., HomeAssistant],
    caplog: pytest.LogCaptureFixture,
    device_class,
    state_unit,
    value,
) -> None:
    """Test compiling hourly statistics, with one sensor being unavailable.

    sensor.test1 is unavailable and should not have statistics generated
    sensor.test2 should have statistics generated
    """
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
    with freeze_time(zero) as freezer:
        _, _states = record_states(hass, freezer, zero, "sensor.test2", attributes)
    states = {**states, **_states}
    hist = history.get_significant_states(
        hass, zero, four, hass.states.async_entity_ids()
    )
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)

    do_adhoc_statistics(hass, start=four)
    wait_recording_done(hass)
    stats = statistics_during_period(hass, four, period="5minute")
    assert stats == {
        "sensor.test2": [
            {
                "start": process_timestamp(four).timestamp(),
                "end": process_timestamp(four + timedelta(minutes=5)).timestamp(),
                "mean": pytest.approx(value),
                "min": pytest.approx(value),
                "max": pytest.approx(value),
                "last_reset": None,
                "state": None,
                "sum": None,
            }
        ]
    }
    assert "Error while processing event StatisticsTask" not in caplog.text


def test_compile_hourly_statistics_fails(
    hass_recorder: Callable[..., HomeAssistant], caplog: pytest.LogCaptureFixture
) -> None:
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
    (
        "state_class",
        "device_class",
        "state_unit",
        "display_unit",
        "statistics_unit",
        "unit_class",
        "statistic_type",
    ),
    [
        ("measurement", "battery", "%", "%", "%", "unitless", "mean"),
        ("measurement", "battery", None, None, None, "unitless", "mean"),
        ("measurement", "distance", "m", "m", "m", "distance", "mean"),
        ("measurement", "distance", "mi", "mi", "mi", "distance", "mean"),
        ("total", "distance", "m", "m", "m", "distance", "sum"),
        ("total", "distance", "mi", "mi", "mi", "distance", "sum"),
        ("total", "energy", "Wh", "Wh", "Wh", "energy", "sum"),
        ("total", "energy", "kWh", "kWh", "kWh", "energy", "sum"),
        ("measurement", "energy", "Wh", "Wh", "Wh", "energy", "mean"),
        ("measurement", "energy", "kWh", "kWh", "kWh", "energy", "mean"),
        ("measurement", "humidity", "%", "%", "%", "unitless", "mean"),
        ("measurement", "humidity", None, None, None, "unitless", "mean"),
        ("total", "monetary", "USD", "USD", "USD", None, "sum"),
        ("total", "monetary", "None", "None", "None", None, "sum"),
        ("total", "gas", "m³", "m³", "m³", "volume", "sum"),
        ("total", "gas", "ft³", "ft³", "ft³", "volume", "sum"),
        ("measurement", "monetary", "USD", "USD", "USD", None, "mean"),
        ("measurement", "monetary", "None", "None", "None", None, "mean"),
        ("measurement", "gas", "m³", "m³", "m³", "volume", "mean"),
        ("measurement", "gas", "ft³", "ft³", "ft³", "volume", "mean"),
        ("measurement", "pressure", "Pa", "Pa", "Pa", "pressure", "mean"),
        ("measurement", "pressure", "hPa", "hPa", "hPa", "pressure", "mean"),
        ("measurement", "pressure", "mbar", "mbar", "mbar", "pressure", "mean"),
        ("measurement", "pressure", "inHg", "inHg", "inHg", "pressure", "mean"),
        ("measurement", "pressure", "psi", "psi", "psi", "pressure", "mean"),
        ("measurement", "speed", "m/s", "m/s", "m/s", "speed", "mean"),
        ("measurement", "speed", "mph", "mph", "mph", "speed", "mean"),
        ("measurement", "temperature", "°C", "°C", "°C", "temperature", "mean"),
        ("measurement", "temperature", "°F", "°F", "°F", "temperature", "mean"),
        ("measurement", "volume", "m³", "m³", "m³", "volume", "mean"),
        ("measurement", "volume", "ft³", "ft³", "ft³", "volume", "mean"),
        ("total", "volume", "m³", "m³", "m³", "volume", "sum"),
        ("total", "volume", "ft³", "ft³", "ft³", "volume", "sum"),
        ("measurement", "weight", "g", "g", "g", "mass", "mean"),
        ("measurement", "weight", "oz", "oz", "oz", "mass", "mean"),
        ("total", "weight", "g", "g", "g", "mass", "sum"),
        ("total", "weight", "oz", "oz", "oz", "mass", "sum"),
    ],
)
def test_list_statistic_ids(
    hass_recorder: Callable[..., HomeAssistant],
    caplog: pytest.LogCaptureFixture,
    state_class,
    device_class,
    state_unit,
    display_unit,
    statistics_unit,
    unit_class,
    statistic_type,
) -> None:
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
            "unit_class": unit_class,
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
                    "unit_class": unit_class,
                },
            ]
        else:
            assert statistic_ids == []


@pytest.mark.parametrize(
    "_attributes",
    [{**ENERGY_SENSOR_ATTRIBUTES, "last_reset": 0}, TEMPERATURE_SENSOR_ATTRIBUTES],
)
def test_list_statistic_ids_unsupported(
    hass_recorder: Callable[..., HomeAssistant],
    caplog: pytest.LogCaptureFixture,
    _attributes,
) -> None:
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
    ("device_class", "state_unit", "state_unit2", "unit_class", "mean", "min", "max"),
    [
        (None, None, "cats", "unitless", 13.050847, -10, 30),
        (None, "%", "cats", "unitless", 13.050847, -10, 30),
        ("battery", "%", "cats", "unitless", 13.050847, -10, 30),
        ("battery", None, "cats", "unitless", 13.050847, -10, 30),
        (None, "kW", "Wh", "power", 13.050847, -10, 30),
        # Can't downgrade from ft³ to ft3 or from m³ to m3
        (None, "ft³", "ft3", "volume", 13.050847, -10, 30),
        (None, "m³", "m3", "volume", 13.050847, -10, 30),
    ],
)
def test_compile_hourly_statistics_changing_units_1(
    hass_recorder: Callable[..., HomeAssistant],
    caplog: pytest.LogCaptureFixture,
    device_class,
    state_unit,
    state_unit2,
    unit_class,
    mean,
    min,
    max,
) -> None:
    """Test compiling hourly statistics where units change from one hour to the next.

    This tests the case where the recorder cannot convert between the units.
    """
    zero = dt_util.utcnow()
    hass = hass_recorder()
    setup_component(hass, "sensor", {})
    wait_recording_done(hass)  # Wait for the sensor recorder platform to be added
    attributes = {
        "device_class": device_class,
        "state_class": "measurement",
        "unit_of_measurement": state_unit,
    }
    with freeze_time(zero) as freezer:
        four, states = record_states(hass, freezer, zero, "sensor.test1", attributes)
        attributes["unit_of_measurement"] = state_unit2
        four, _states = record_states(
            hass, freezer, zero + timedelta(minutes=5), "sensor.test1", attributes
        )
        states["sensor.test1"] += _states["sensor.test1"]
        four, _states = record_states(
            hass, freezer, zero + timedelta(minutes=10), "sensor.test1", attributes
        )
        states["sensor.test1"] += _states["sensor.test1"]
    hist = history.get_significant_states(
        hass, zero, four, hass.states.async_entity_ids()
    )
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)

    do_adhoc_statistics(hass, start=zero)
    wait_recording_done(hass)
    assert "cannot be converted to the unit of previously" not in caplog.text
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
            "unit_class": unit_class,
        },
    ]
    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {
        "sensor.test1": [
            {
                "start": process_timestamp(zero).timestamp(),
                "end": process_timestamp(zero + timedelta(minutes=5)).timestamp(),
                "mean": pytest.approx(mean),
                "min": pytest.approx(min),
                "max": pytest.approx(max),
                "last_reset": None,
                "state": None,
                "sum": None,
            }
        ]
    }

    do_adhoc_statistics(hass, start=zero + timedelta(minutes=10))
    wait_recording_done(hass)
    assert (
        f"The unit of sensor.test1 ({state_unit2}) cannot be converted to the unit of "
        f"previously compiled statistics ({state_unit})" in caplog.text
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
            "unit_class": unit_class,
        },
    ]
    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {
        "sensor.test1": [
            {
                "start": process_timestamp(zero).timestamp(),
                "end": process_timestamp(zero + timedelta(minutes=5)).timestamp(),
                "mean": pytest.approx(mean),
                "min": pytest.approx(min),
                "max": pytest.approx(max),
                "last_reset": None,
                "state": None,
                "sum": None,
            }
        ]
    }
    assert "Error while processing event StatisticsTask" not in caplog.text


@pytest.mark.parametrize(
    (
        "device_class",
        "state_unit",
        "display_unit",
        "statistics_unit",
        "unit_class",
        "mean",
        "min",
        "max",
    ),
    [
        (None, "dogs", "dogs", "dogs", None, 13.050847, -10, 30),
    ],
)
def test_compile_hourly_statistics_changing_units_2(
    hass_recorder: Callable[..., HomeAssistant],
    caplog: pytest.LogCaptureFixture,
    device_class,
    state_unit,
    display_unit,
    statistics_unit,
    unit_class,
    mean,
    min,
    max,
) -> None:
    """Test compiling hourly statistics where units change during an hour.

    This tests the behaviour when the sensor units are note supported by any unit
    converter.
    """
    zero = dt_util.utcnow()
    hass = hass_recorder()
    setup_component(hass, "sensor", {})
    wait_recording_done(hass)  # Wait for the sensor recorder platform to be added
    attributes = {
        "device_class": device_class,
        "state_class": "measurement",
        "unit_of_measurement": state_unit,
    }
    with freeze_time(zero) as freezer:
        four, states = record_states(hass, freezer, zero, "sensor.test1", attributes)
        attributes["unit_of_measurement"] = "cats"
        four, _states = record_states(
            hass, freezer, zero + timedelta(minutes=5), "sensor.test1", attributes
        )
        states["sensor.test1"] += _states["sensor.test1"]
    hist = history.get_significant_states(
        hass, zero, four, hass.states.async_entity_ids()
    )
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)

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
            "unit_class": unit_class,
        },
    ]
    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {}

    assert "Error while processing event StatisticsTask" not in caplog.text


@pytest.mark.parametrize(
    (
        "device_class",
        "state_unit",
        "display_unit",
        "statistics_unit",
        "unit_class",
        "mean",
        "min",
        "max",
    ),
    [
        (None, "dogs", "dogs", "dogs", None, 13.050847, -10, 30),
    ],
)
def test_compile_hourly_statistics_changing_units_3(
    hass_recorder: Callable[..., HomeAssistant],
    caplog: pytest.LogCaptureFixture,
    device_class,
    state_unit,
    display_unit,
    statistics_unit,
    unit_class,
    mean,
    min,
    max,
) -> None:
    """Test compiling hourly statistics where units change from one hour to the next.

    This tests the behaviour when the sensor units are note supported by any unit
    converter.
    """
    zero = dt_util.utcnow()
    hass = hass_recorder()
    setup_component(hass, "sensor", {})
    wait_recording_done(hass)  # Wait for the sensor recorder platform to be added
    attributes = {
        "device_class": device_class,
        "state_class": "measurement",
        "unit_of_measurement": state_unit,
    }
    with freeze_time(zero) as freezer:
        four, states = record_states(hass, freezer, zero, "sensor.test1", attributes)
        four, _states = record_states(
            hass, freezer, zero + timedelta(minutes=5), "sensor.test1", attributes
        )
        states["sensor.test1"] += _states["sensor.test1"]
        attributes["unit_of_measurement"] = "cats"
        four, _states = record_states(
            hass, freezer, zero + timedelta(minutes=10), "sensor.test1", attributes
        )
        states["sensor.test1"] += _states["sensor.test1"]
    hist = history.get_significant_states(
        hass, zero, four, hass.states.async_entity_ids()
    )
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)

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
            "unit_class": unit_class,
        },
    ]
    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {
        "sensor.test1": [
            {
                "start": process_timestamp(zero).timestamp(),
                "end": process_timestamp(zero + timedelta(minutes=5)).timestamp(),
                "mean": pytest.approx(mean),
                "min": pytest.approx(min),
                "max": pytest.approx(max),
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
            "unit_class": unit_class,
        },
    ]
    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {
        "sensor.test1": [
            {
                "start": process_timestamp(zero).timestamp(),
                "end": process_timestamp(zero + timedelta(minutes=5)).timestamp(),
                "mean": pytest.approx(mean),
                "min": pytest.approx(min),
                "max": pytest.approx(max),
                "last_reset": None,
                "state": None,
                "sum": None,
            }
        ]
    }
    assert "Error while processing event StatisticsTask" not in caplog.text


@pytest.mark.parametrize(
    ("state_unit_1", "state_unit_2", "unit_class", "mean", "min", "max", "factor"),
    [
        (None, "%", "unitless", 13.050847, -10, 30, 100),
        ("%", None, "unitless", 13.050847, -10, 30, 0.01),
        ("W", "kW", "power", 13.050847, -10, 30, 0.001),
        ("kW", "W", "power", 13.050847, -10, 30, 1000),
    ],
)
def test_compile_hourly_statistics_convert_units_1(
    hass_recorder: Callable[..., HomeAssistant],
    caplog: pytest.LogCaptureFixture,
    state_unit_1,
    state_unit_2,
    unit_class,
    mean,
    min,
    max,
    factor,
) -> None:
    """Test compiling hourly statistics where units change from one hour to the next.

    This tests the case where the recorder can convert between the units.
    """
    zero = dt_util.utcnow()
    hass = hass_recorder()
    setup_component(hass, "sensor", {})
    wait_recording_done(hass)  # Wait for the sensor recorder platform to be added
    attributes = {
        "device_class": None,
        "state_class": "measurement",
        "unit_of_measurement": state_unit_1,
    }
    with freeze_time(zero) as freezer:
        four, states = record_states(hass, freezer, zero, "sensor.test1", attributes)
        four, _states = record_states(
            hass,
            freezer,
            zero + timedelta(minutes=5),
            "sensor.test1",
            attributes,
            seq=[0, 1, None],
        )
    states["sensor.test1"] += _states["sensor.test1"]

    do_adhoc_statistics(hass, start=zero)
    wait_recording_done(hass)
    assert "does not match the unit of already compiled" not in caplog.text
    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {
            "statistic_id": "sensor.test1",
            "display_unit_of_measurement": state_unit_1,
            "has_mean": True,
            "has_sum": False,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": state_unit_1,
            "unit_class": unit_class,
        },
    ]
    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {
        "sensor.test1": [
            {
                "start": process_timestamp(zero).timestamp(),
                "end": process_timestamp(zero + timedelta(minutes=5)).timestamp(),
                "mean": pytest.approx(mean),
                "min": pytest.approx(min),
                "max": pytest.approx(max),
                "last_reset": None,
                "state": None,
                "sum": None,
            }
        ]
    }

    attributes["unit_of_measurement"] = state_unit_2
    with freeze_time(four) as freezer:
        four, _states = record_states(
            hass, freezer, zero + timedelta(minutes=10), "sensor.test1", attributes
        )
    states["sensor.test1"] += _states["sensor.test1"]
    hist = history.get_significant_states(
        hass, zero, four, hass.states.async_entity_ids()
    )
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)
    do_adhoc_statistics(hass, start=zero + timedelta(minutes=10))
    wait_recording_done(hass)
    assert "The unit of sensor.test1 is changing" not in caplog.text
    assert (
        f"matches the unit of already compiled statistics ({state_unit_1})"
        not in caplog.text
    )
    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {
            "statistic_id": "sensor.test1",
            "display_unit_of_measurement": state_unit_2,
            "has_mean": True,
            "has_sum": False,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": state_unit_1,
            "unit_class": unit_class,
        },
    ]
    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {
        "sensor.test1": [
            {
                "start": process_timestamp(zero).timestamp(),
                "end": process_timestamp(zero + timedelta(minutes=5)).timestamp(),
                "mean": pytest.approx(mean * factor),
                "min": pytest.approx(min * factor),
                "max": pytest.approx(max * factor),
                "last_reset": None,
                "state": None,
                "sum": None,
            },
            {
                "start": process_timestamp(zero + timedelta(minutes=10)).timestamp(),
                "end": process_timestamp(zero + timedelta(minutes=15)).timestamp(),
                "mean": pytest.approx(mean),
                "min": pytest.approx(min),
                "max": pytest.approx(max),
                "last_reset": None,
                "state": None,
                "sum": None,
            },
        ]
    }
    assert "Error while processing event StatisticsTask" not in caplog.text


@pytest.mark.parametrize(
    (
        "device_class",
        "state_unit",
        "state_unit2",
        "unit_class",
        "unit_class2",
        "mean",
        "mean2",
        "min",
        "max",
    ),
    [
        (None, "RPM", "rpm", None, None, 13.050847, 13.333333, -10, 30),
        (None, "rpm", "RPM", None, None, 13.050847, 13.333333, -10, 30),
        (None, "ft3", "ft³", None, "volume", 13.050847, 13.333333, -10, 30),
        (None, "m3", "m³", None, "volume", 13.050847, 13.333333, -10, 30),
    ],
)
def test_compile_hourly_statistics_equivalent_units_1(
    hass_recorder: Callable[..., HomeAssistant],
    caplog: pytest.LogCaptureFixture,
    device_class,
    state_unit,
    state_unit2,
    unit_class,
    unit_class2,
    mean,
    mean2,
    min,
    max,
) -> None:
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
    with freeze_time(zero) as freezer:
        four, states = record_states(hass, freezer, zero, "sensor.test1", attributes)
        attributes["unit_of_measurement"] = state_unit2
        four, _states = record_states(
            hass, freezer, zero + timedelta(minutes=5), "sensor.test1", attributes
        )
        states["sensor.test1"] += _states["sensor.test1"]
        four, _states = record_states(
            hass, freezer, zero + timedelta(minutes=10), "sensor.test1", attributes
        )
    states["sensor.test1"] += _states["sensor.test1"]
    hist = history.get_significant_states(
        hass, zero, four, hass.states.async_entity_ids()
    )
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)

    do_adhoc_statistics(hass, start=zero)
    wait_recording_done(hass)
    assert "cannot be converted to the unit of previously" not in caplog.text
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
            "unit_class": unit_class,
        },
    ]
    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {
        "sensor.test1": [
            {
                "start": process_timestamp(zero).timestamp(),
                "end": process_timestamp(zero + timedelta(minutes=5)).timestamp(),
                "mean": pytest.approx(mean),
                "min": pytest.approx(min),
                "max": pytest.approx(max),
                "last_reset": None,
                "state": None,
                "sum": None,
            }
        ]
    }

    do_adhoc_statistics(hass, start=zero + timedelta(minutes=10))
    wait_recording_done(hass)
    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {
            "statistic_id": "sensor.test1",
            "display_unit_of_measurement": state_unit2,
            "has_mean": True,
            "has_sum": False,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": state_unit2,
            "unit_class": unit_class2,
        },
    ]
    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {
        "sensor.test1": [
            {
                "start": process_timestamp(zero).timestamp(),
                "end": process_timestamp(zero + timedelta(minutes=5)).timestamp(),
                "mean": pytest.approx(mean),
                "min": pytest.approx(min),
                "max": pytest.approx(max),
                "last_reset": None,
                "state": None,
                "sum": None,
            },
            {
                "start": process_timestamp(zero + timedelta(minutes=10)).timestamp(),
                "end": process_timestamp(zero + timedelta(minutes=15)).timestamp(),
                "mean": pytest.approx(mean2),
                "min": pytest.approx(min),
                "max": pytest.approx(max),
                "last_reset": None,
                "state": None,
                "sum": None,
            },
        ]
    }
    assert "Error while processing event StatisticsTask" not in caplog.text


@pytest.mark.parametrize(
    ("device_class", "state_unit", "state_unit2", "unit_class", "mean", "min", "max"),
    [
        (None, "RPM", "rpm", None, 13.333333, -10, 30),
        (None, "rpm", "RPM", None, 13.333333, -10, 30),
        (None, "ft3", "ft³", None, 13.333333, -10, 30),
        (None, "m3", "m³", None, 13.333333, -10, 30),
    ],
)
def test_compile_hourly_statistics_equivalent_units_2(
    hass_recorder: Callable[..., HomeAssistant],
    caplog: pytest.LogCaptureFixture,
    device_class,
    state_unit,
    state_unit2,
    unit_class,
    mean,
    min,
    max,
) -> None:
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
    with freeze_time(zero) as freezer:
        four, states = record_states(hass, freezer, zero, "sensor.test1", attributes)
        attributes["unit_of_measurement"] = state_unit2
        four, _states = record_states(
            hass, freezer, zero + timedelta(minutes=5), "sensor.test1", attributes
        )
    states["sensor.test1"] += _states["sensor.test1"]
    hist = history.get_significant_states(
        hass, zero, four, hass.states.async_entity_ids()
    )
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)

    do_adhoc_statistics(hass, start=zero + timedelta(seconds=30 * 5))
    wait_recording_done(hass)
    assert "The unit of sensor.test1 is changing" not in caplog.text
    assert "and matches the unit of already compiled statistics" not in caplog.text
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
            "unit_class": unit_class,
        },
    ]
    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {
        "sensor.test1": [
            {
                "start": process_timestamp(
                    zero + timedelta(seconds=30 * 5)
                ).timestamp(),
                "end": process_timestamp(zero + timedelta(seconds=30 * 15)).timestamp(),
                "mean": pytest.approx(mean),
                "min": pytest.approx(min),
                "max": pytest.approx(max),
                "last_reset": None,
                "state": None,
                "sum": None,
            },
        ]
    }

    assert "Error while processing event StatisticsTask" not in caplog.text


@pytest.mark.parametrize(
    (
        "device_class",
        "state_unit",
        "statistic_unit",
        "unit_class",
        "mean1",
        "mean2",
        "min",
        "max",
    ),
    [
        ("power", "kW", "kW", "power", 13.050847, 13.333333, -10, 30),
    ],
)
def test_compile_hourly_statistics_changing_device_class_1(
    hass_recorder: Callable[..., HomeAssistant],
    caplog: pytest.LogCaptureFixture,
    device_class,
    state_unit,
    statistic_unit,
    unit_class,
    mean1,
    mean2,
    min,
    max,
) -> None:
    """Test compiling hourly statistics where device class changes from one hour to the next.

    Device class is ignored, meaning changing device class should not influence the statistics.
    """
    zero = dt_util.utcnow()
    hass = hass_recorder()
    setup_component(hass, "sensor", {})
    wait_recording_done(hass)  # Wait for the sensor recorder platform to be added

    # Record some states for an initial period, the entity has no device class
    attributes = {
        "state_class": "measurement",
        "unit_of_measurement": state_unit,
    }
    with freeze_time(zero) as freezer:
        four, states = record_states(hass, freezer, zero, "sensor.test1", attributes)

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
            "unit_class": unit_class,
        },
    ]
    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {
        "sensor.test1": [
            {
                "start": process_timestamp(zero).timestamp(),
                "end": process_timestamp(zero + timedelta(minutes=5)).timestamp(),
                "mean": pytest.approx(mean1),
                "min": pytest.approx(min),
                "max": pytest.approx(max),
                "last_reset": None,
                "state": None,
                "sum": None,
            }
        ]
    }

    # Update device class and record additional states in the original UoM
    attributes["device_class"] = device_class
    with freeze_time(zero) as freezer:
        four, _states = record_states(
            hass, freezer, zero + timedelta(minutes=5), "sensor.test1", attributes
        )
        states["sensor.test1"] += _states["sensor.test1"]
        four, _states = record_states(
            hass, freezer, zero + timedelta(minutes=10), "sensor.test1", attributes
        )
    states["sensor.test1"] += _states["sensor.test1"]
    hist = history.get_significant_states(
        hass, zero, four, hass.states.async_entity_ids()
    )
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)

    # Run statistics again, additional statistics is generated
    do_adhoc_statistics(hass, start=zero + timedelta(minutes=10))
    wait_recording_done(hass)
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
            "unit_class": unit_class,
        },
    ]
    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {
        "sensor.test1": [
            {
                "start": process_timestamp(zero).timestamp(),
                "end": process_timestamp(zero + timedelta(minutes=5)).timestamp(),
                "mean": pytest.approx(mean1),
                "min": pytest.approx(min),
                "max": pytest.approx(max),
                "last_reset": None,
                "state": None,
                "sum": None,
            },
            {
                "start": process_timestamp(zero + timedelta(minutes=10)).timestamp(),
                "end": process_timestamp(zero + timedelta(minutes=15)).timestamp(),
                "mean": pytest.approx(mean2),
                "min": pytest.approx(min),
                "max": pytest.approx(max),
                "last_reset": None,
                "state": None,
                "sum": None,
            },
        ]
    }

    # Update device class and record additional states in a different UoM
    attributes["unit_of_measurement"] = statistic_unit
    with freeze_time(zero) as freezer:
        four, _states = record_states(
            hass, freezer, zero + timedelta(minutes=15), "sensor.test1", attributes
        )
        states["sensor.test1"] += _states["sensor.test1"]
        four, _states = record_states(
            hass, freezer, zero + timedelta(minutes=20), "sensor.test1", attributes
        )
    states["sensor.test1"] += _states["sensor.test1"]
    hist = history.get_significant_states(
        hass, zero, four, hass.states.async_entity_ids()
    )
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)

    # Run statistics again, additional statistics is generated
    do_adhoc_statistics(hass, start=zero + timedelta(minutes=20))
    wait_recording_done(hass)
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
            "unit_class": unit_class,
        },
    ]
    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {
        "sensor.test1": [
            {
                "start": process_timestamp(zero).timestamp(),
                "end": process_timestamp(zero + timedelta(minutes=5)).timestamp(),
                "mean": pytest.approx(mean1),
                "min": pytest.approx(min),
                "max": pytest.approx(max),
                "last_reset": None,
                "state": None,
                "sum": None,
            },
            {
                "start": process_timestamp(zero + timedelta(minutes=10)).timestamp(),
                "end": process_timestamp(zero + timedelta(minutes=15)).timestamp(),
                "mean": pytest.approx(mean2),
                "min": pytest.approx(min),
                "max": pytest.approx(max),
                "last_reset": None,
                "state": None,
                "sum": None,
            },
            {
                "start": process_timestamp(zero + timedelta(minutes=20)).timestamp(),
                "end": process_timestamp(zero + timedelta(minutes=25)).timestamp(),
                "mean": pytest.approx(mean2),
                "min": pytest.approx(min),
                "max": pytest.approx(max),
                "last_reset": None,
                "state": None,
                "sum": None,
            },
        ]
    }
    assert "Error while processing event StatisticsTask" not in caplog.text


@pytest.mark.parametrize(
    (
        "device_class",
        "state_unit",
        "display_unit",
        "statistic_unit",
        "unit_class",
        "mean",
        "mean2",
        "min",
        "max",
    ),
    [
        ("power", "kW", "kW", "kW", "power", 13.050847, 13.333333, -10, 30),
    ],
)
def test_compile_hourly_statistics_changing_device_class_2(
    hass_recorder: Callable[..., HomeAssistant],
    caplog: pytest.LogCaptureFixture,
    device_class,
    state_unit,
    display_unit,
    statistic_unit,
    unit_class,
    mean,
    mean2,
    min,
    max,
) -> None:
    """Test compiling hourly statistics where device class changes from one hour to the next.

    Device class is ignored, meaning changing device class should not influence the statistics.
    """
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
    with freeze_time(zero) as freezer:
        four, states = record_states(hass, freezer, zero, "sensor.test1", attributes)

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
            "statistics_unit_of_measurement": statistic_unit,
            "unit_class": unit_class,
        },
    ]
    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {
        "sensor.test1": [
            {
                "start": process_timestamp(zero).timestamp(),
                "end": process_timestamp(zero + timedelta(minutes=5)).timestamp(),
                "mean": pytest.approx(mean),
                "min": pytest.approx(min),
                "max": pytest.approx(max),
                "last_reset": None,
                "state": None,
                "sum": None,
            }
        ]
    }

    # Remove device class and record additional states
    attributes.pop("device_class")
    with freeze_time(zero) as freezer:
        four, _states = record_states(
            hass, freezer, zero + timedelta(minutes=5), "sensor.test1", attributes
        )
        states["sensor.test1"] += _states["sensor.test1"]
        four, _states = record_states(
            hass, freezer, zero + timedelta(minutes=10), "sensor.test1", attributes
        )
    states["sensor.test1"] += _states["sensor.test1"]
    hist = history.get_significant_states(
        hass, zero, four, hass.states.async_entity_ids()
    )
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)

    # Run statistics again, additional statistics is generated
    do_adhoc_statistics(hass, start=zero + timedelta(minutes=10))
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
            "statistics_unit_of_measurement": statistic_unit,
            "unit_class": unit_class,
        },
    ]
    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {
        "sensor.test1": [
            {
                "start": process_timestamp(zero).timestamp(),
                "end": process_timestamp(zero + timedelta(minutes=5)).timestamp(),
                "mean": pytest.approx(mean),
                "min": pytest.approx(min),
                "max": pytest.approx(max),
                "last_reset": None,
                "state": None,
                "sum": None,
            },
            {
                "start": process_timestamp(zero + timedelta(minutes=10)).timestamp(),
                "end": process_timestamp(zero + timedelta(minutes=15)).timestamp(),
                "mean": pytest.approx(mean2),
                "min": pytest.approx(min),
                "max": pytest.approx(max),
                "last_reset": None,
                "state": None,
                "sum": None,
            },
        ]
    }
    assert "Error while processing event StatisticsTask" not in caplog.text


@pytest.mark.parametrize(
    (
        "device_class",
        "state_unit",
        "display_unit",
        "statistics_unit",
        "unit_class",
        "mean",
        "min",
        "max",
    ),
    [
        (None, None, None, None, "unitless", 13.050847, -10, 30),
    ],
)
def test_compile_hourly_statistics_changing_state_class(
    hass_recorder: Callable[..., HomeAssistant],
    caplog: pytest.LogCaptureFixture,
    device_class,
    state_unit,
    display_unit,
    statistics_unit,
    unit_class,
    mean,
    min,
    max,
) -> None:
    """Test compiling hourly statistics where state class changes."""
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
    with freeze_time(period0) as freezer:
        four, states = record_states(
            hass, freezer, period0, "sensor.test1", attributes_1
        )
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
            "unit_class": unit_class,
        },
    ]
    metadata = get_metadata(hass, statistic_ids={"sensor.test1"})
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
    with freeze_time(period1) as freezer:
        four, _states = record_states(
            hass, freezer, period1, "sensor.test1", attributes_2
        )
    states["sensor.test1"] += _states["sensor.test1"]
    hist = history.get_significant_states(
        hass, period0, four, hass.states.async_entity_ids()
    )
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)

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
            "unit_class": unit_class,
        },
    ]
    metadata = get_metadata(hass, statistic_ids={"sensor.test1"})
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
                "start": process_timestamp(period0).timestamp(),
                "end": process_timestamp(period0_end).timestamp(),
                "mean": pytest.approx(mean),
                "min": pytest.approx(min),
                "max": pytest.approx(max),
                "last_reset": None,
                "state": None,
                "sum": None,
            },
            {
                "start": process_timestamp(period1).timestamp(),
                "end": process_timestamp(period1_end).timestamp(),
                "mean": None,
                "min": None,
                "max": None,
                "last_reset": None,
                "state": pytest.approx(30.0),
                "sum": pytest.approx(30.0),
            },
        ]
    }

    assert "Error while processing event StatisticsTask" not in caplog.text


@pytest.mark.timeout(25)
def test_compile_statistics_hourly_daily_monthly_summary(
    hass_recorder: Callable[..., HomeAssistant], caplog: pytest.LogCaptureFixture
) -> None:
    """Test compiling hourly statistics + monthly and daily summary."""
    zero = dt_util.utcnow()
    # August 31st, 23:00 local time
    zero = zero.replace(
        year=2021, month=9, day=1, hour=5, minute=0, second=0, microsecond=0
    )
    with freeze_time(zero):
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
    with freeze_time(start) as freezer:
        for i in range(24):
            seq = [-10, 15, 30]
            # test1 has same value in every period
            four, _states = record_states(
                hass, freezer, start, "sensor.test1", attributes, seq
            )
            states["sensor.test1"] += _states["sensor.test1"]
            last_state = last_states["sensor.test1"]
            expected_minima["sensor.test1"].append(_min(seq, last_state))
            expected_maxima["sensor.test1"].append(_max(seq, last_state))
            expected_averages["sensor.test1"].append(
                _weighted_average(seq, i, last_state)
            )
            last_states["sensor.test1"] = seq[-1]
            # test2 values change: min/max at the last state
            seq = [-10 * (i + 1), 15 * (i + 1), 30 * (i + 1)]
            four, _states = record_states(
                hass, freezer, start, "sensor.test2", attributes, seq
            )
            states["sensor.test2"] += _states["sensor.test2"]
            last_state = last_states["sensor.test2"]
            expected_minima["sensor.test2"].append(_min(seq, last_state))
            expected_maxima["sensor.test2"].append(_max(seq, last_state))
            expected_averages["sensor.test2"].append(
                _weighted_average(seq, i, last_state)
            )
            last_states["sensor.test2"] = seq[-1]
            # test3 values change: min/max at the first state
            seq = [-10 * (23 - i + 1), 15 * (23 - i + 1), 30 * (23 - i + 1)]
            four, _states = record_states(
                hass, freezer, start, "sensor.test3", attributes, seq
            )
            states["sensor.test3"] += _states["sensor.test3"]
            last_state = last_states["sensor.test3"]
            expected_minima["sensor.test3"].append(_min(seq, last_state))
            expected_maxima["sensor.test3"].append(_max(seq, last_state))
            expected_averages["sensor.test3"].append(
                _weighted_average(seq, i, last_state)
            )
            last_states["sensor.test3"] = seq[-1]
            # test4 values grow
            seq = [i, i + 0.5, i + 0.75]
            start_meter = start
            for j in range(len(seq)):
                _states = record_meter_state(
                    hass,
                    freezer,
                    start_meter,
                    "sensor.test4",
                    sum_attributes,
                    seq[j : j + 1],
                )
                start_meter += timedelta(minutes=1)
                states["sensor.test4"] += _states["sensor.test4"]
            last_state = last_states["sensor.test4"]
            expected_states["sensor.test4"].append(seq[-1])
            expected_sums["sensor.test4"].append(
                _sum(seq, last_state, expected_sums["sensor.test4"])
            )
            last_states["sensor.test4"] = seq[-1]

            start += timedelta(minutes=5)
    hist = history.get_significant_states(
        hass,
        zero - timedelta.resolution,
        four,
        hass.states.async_entity_ids(),
        significant_changes_only=False,
    )
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)
    wait_recording_done(hass)

    # Generate 5-minute statistics for two hours
    start = zero
    for _ in range(24):
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
            "unit_class": "unitless",
        },
        {
            "statistic_id": "sensor.test2",
            "display_unit_of_measurement": "%",
            "has_mean": True,
            "has_sum": False,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": "%",
            "unit_class": "unitless",
        },
        {
            "statistic_id": "sensor.test3",
            "display_unit_of_measurement": "%",
            "has_mean": True,
            "has_sum": False,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": "%",
            "unit_class": "unitless",
        },
        {
            "statistic_id": "sensor.test4",
            "display_unit_of_measurement": "EUR",
            "has_mean": False,
            "has_sum": True,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": "EUR",
            "unit_class": None,
        },
    ]

    # Adjust the inserted statistics
    sum_adjustment = -10
    sum_adjustement_start = zero + timedelta(minutes=65)
    for i in range(13, 24):
        expected_sums["sensor.test4"][i] += sum_adjustment
    instance.async_adjust_statistics(
        "sensor.test4", sum_adjustement_start, sum_adjustment, "EUR"
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
                    "start": process_timestamp(start).timestamp(),
                    "end": process_timestamp(end).timestamp(),
                    "mean": pytest.approx(expected_average),
                    "min": pytest.approx(expected_minimum),
                    "max": pytest.approx(expected_maximum),
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
                    "start": process_timestamp(start).timestamp(),
                    "end": process_timestamp(end).timestamp(),
                    "mean": pytest.approx(expected_average),
                    "min": pytest.approx(expected_minimum),
                    "max": pytest.approx(expected_maximum),
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
                    "start": process_timestamp(start).timestamp(),
                    "end": process_timestamp(end).timestamp(),
                    "mean": pytest.approx(expected_average),
                    "min": pytest.approx(expected_minimum),
                    "max": pytest.approx(expected_maximum),
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
                    "start": process_timestamp(start).timestamp(),
                    "end": process_timestamp(end).timestamp(),
                    "mean": pytest.approx(expected_average),
                    "min": pytest.approx(expected_minimum),
                    "max": pytest.approx(expected_maximum),
                    "last_reset": None,
                    "state": expected_state,
                    "sum": expected_sum,
                }
            )
        start = (start + timedelta(days=31)).replace(day=1)
        end = (end + timedelta(days=31)).replace(day=1)
    assert stats == expected_stats

    assert "Error while processing event StatisticsTask" not in caplog.text


def record_states(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    zero: datetime,
    entity_id: str,
    attributes,
    seq=None,
):
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
    freezer.move_to(one)
    states[entity_id].append(set_state(entity_id, str(seq[0]), attributes=attributes))

    freezer.move_to(two)
    states[entity_id].append(set_state(entity_id, str(seq[1]), attributes=attributes))

    freezer.move_to(three)
    states[entity_id].append(set_state(entity_id, str(seq[2]), attributes=attributes))

    return four, states


@pytest.mark.parametrize(
    ("units", "attributes", "unit", "unit2", "supported_unit"),
    [
        (US_CUSTOMARY_SYSTEM, POWER_SENSOR_ATTRIBUTES, "W", "kW", "W, kW"),
        (METRIC_SYSTEM, POWER_SENSOR_ATTRIBUTES, "W", "kW", "W, kW"),
        (
            US_CUSTOMARY_SYSTEM,
            TEMPERATURE_SENSOR_ATTRIBUTES,
            "°F",
            "K",
            "K, °C, °F",
        ),
        (METRIC_SYSTEM, TEMPERATURE_SENSOR_ATTRIBUTES, "°C", "K", "K, °C, °F"),
        (
            US_CUSTOMARY_SYSTEM,
            PRESSURE_SENSOR_ATTRIBUTES,
            "psi",
            "bar",
            "Pa, bar, cbar, hPa, inHg, kPa, mbar, mmHg, psi",
        ),
        (
            METRIC_SYSTEM,
            PRESSURE_SENSOR_ATTRIBUTES,
            "Pa",
            "bar",
            "Pa, bar, cbar, hPa, inHg, kPa, mbar, mmHg, psi",
        ),
    ],
)
async def test_validate_unit_change_convertible(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    units,
    attributes,
    unit,
    unit2,
    supported_unit,
) -> None:
    """Test validate_statistics.

    This tests what happens if a sensor is first recorded in a unit which supports unit
    conversion, and the unit is then changed to a unit which can and cannot be
    converted to the original unit.

    The test also asserts that the sensor's device class is ignored.
    """
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

    # No statistics, unit in state matching device class - empty response
    hass.states.async_set(
        "sensor.test", 10, attributes={**attributes, **{"unit_of_measurement": unit}}
    )
    await async_recorder_block_till_done(hass)
    await assert_validation_result(client, {})

    # No statistics, unit in state not matching device class - empty response
    hass.states.async_set(
        "sensor.test", 11, attributes={**attributes, **{"unit_of_measurement": "dogs"}}
    )
    await async_recorder_block_till_done(hass)
    await assert_validation_result(client, {})

    # Statistics has run, incompatible unit - expect error
    await async_recorder_block_till_done(hass)
    do_adhoc_statistics(hass, start=now)
    hass.states.async_set(
        "sensor.test", 12, attributes={**attributes, **{"unit_of_measurement": "dogs"}}
    )
    await async_recorder_block_till_done(hass)
    expected = {
        "sensor.test": [
            {
                "data": {
                    "metadata_unit": unit,
                    "state_unit": "dogs",
                    "statistic_id": "sensor.test",
                    "supported_unit": supported_unit,
                },
                "type": "units_changed",
            }
        ],
    }
    await assert_validation_result(client, expected)

    # Valid state - empty response
    hass.states.async_set(
        "sensor.test", 13, attributes={**attributes, **{"unit_of_measurement": unit}}
    )
    await async_recorder_block_till_done(hass)
    await assert_validation_result(client, {})

    # Valid state, statistic runs again - empty response
    do_adhoc_statistics(hass, start=now + timedelta(hours=1))
    await async_recorder_block_till_done(hass)
    await assert_validation_result(client, {})

    # Valid state in compatible unit - empty response
    hass.states.async_set(
        "sensor.test", 13, attributes={**attributes, **{"unit_of_measurement": unit2}}
    )
    await async_recorder_block_till_done(hass)
    await assert_validation_result(client, {})

    # Valid state, statistic runs again - empty response
    do_adhoc_statistics(hass, start=now + timedelta(hours=2))
    await async_recorder_block_till_done(hass)
    await assert_validation_result(client, {})

    # Remove the state - expect error about missing state
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
    ("units", "attributes"),
    [
        (US_CUSTOMARY_SYSTEM, POWER_SENSOR_ATTRIBUTES),
    ],
)
async def test_validate_statistics_unit_ignore_device_class(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    units,
    attributes,
) -> None:
    """Test validate_statistics.

    The test asserts that the sensor's device class is ignored.
    """
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

    # No statistics, no device class - empty response
    initial_attributes = {"state_class": "measurement", "unit_of_measurement": "dogs"}
    hass.states.async_set("sensor.test", 10, attributes=initial_attributes)
    await hass.async_block_till_done()
    await assert_validation_result(client, {})

    # Statistics has run, device class set not matching unit - empty response
    do_adhoc_statistics(hass, start=now)
    await async_recorder_block_till_done(hass)
    hass.states.async_set(
        "sensor.test", 12, attributes={**attributes, **{"unit_of_measurement": "dogs"}}
    )
    await hass.async_block_till_done()
    await assert_validation_result(client, {})


@pytest.mark.parametrize(
    ("units", "attributes", "unit", "unit2", "supported_unit"),
    [
        (US_CUSTOMARY_SYSTEM, POWER_SENSOR_ATTRIBUTES, "W", "kW", "W, kW"),
        (METRIC_SYSTEM, POWER_SENSOR_ATTRIBUTES, "W", "kW", "W, kW"),
        (
            US_CUSTOMARY_SYSTEM,
            TEMPERATURE_SENSOR_ATTRIBUTES,
            "°F",
            "K",
            "K, °C, °F",
        ),
        (METRIC_SYSTEM, TEMPERATURE_SENSOR_ATTRIBUTES, "°C", "K", "K, °C, °F"),
        (
            US_CUSTOMARY_SYSTEM,
            PRESSURE_SENSOR_ATTRIBUTES,
            "psi",
            "bar",
            "Pa, bar, cbar, hPa, inHg, kPa, mbar, mmHg, psi",
        ),
        (
            METRIC_SYSTEM,
            PRESSURE_SENSOR_ATTRIBUTES,
            "Pa",
            "bar",
            "Pa, bar, cbar, hPa, inHg, kPa, mbar, mmHg, psi",
        ),
        (
            METRIC_SYSTEM,
            BATTERY_SENSOR_ATTRIBUTES,
            "%",
            None,
            "%, <None>",
        ),
    ],
)
async def test_validate_statistics_unit_change_no_device_class(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    units,
    attributes,
    unit,
    unit2,
    supported_unit,
) -> None:
    """Test validate_statistics.

    This tests what happens if a sensor is first recorded in a unit which supports unit
    conversion, and the unit is then changed to a unit which can and cannot be
    converted to the original unit.
    """
    id = 1
    attributes = dict(attributes)
    attributes.pop("device_class")

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

    # No statistics, sensor state set - empty response
    hass.states.async_set(
        "sensor.test", 10, attributes={**attributes, **{"unit_of_measurement": unit}}
    )
    await async_recorder_block_till_done(hass)
    await assert_validation_result(client, {})

    # No statistics, sensor state set to an incompatible unit - empty response
    hass.states.async_set(
        "sensor.test", 11, attributes={**attributes, **{"unit_of_measurement": "dogs"}}
    )
    await async_recorder_block_till_done(hass)
    await assert_validation_result(client, {})

    # Statistics has run, incompatible unit - expect error
    await async_recorder_block_till_done(hass)
    do_adhoc_statistics(hass, start=now)
    hass.states.async_set(
        "sensor.test", 12, attributes={**attributes, **{"unit_of_measurement": "dogs"}}
    )
    await async_recorder_block_till_done(hass)
    expected = {
        "sensor.test": [
            {
                "data": {
                    "metadata_unit": unit,
                    "state_unit": "dogs",
                    "statistic_id": "sensor.test",
                    "supported_unit": supported_unit,
                },
                "type": "units_changed",
            }
        ],
    }
    await assert_validation_result(client, expected)

    # Valid state - empty response
    hass.states.async_set(
        "sensor.test", 13, attributes={**attributes, **{"unit_of_measurement": unit}}
    )
    await async_recorder_block_till_done(hass)
    await assert_validation_result(client, {})

    # Valid state, statistic runs again - empty response
    do_adhoc_statistics(hass, start=now + timedelta(hours=1))
    await async_recorder_block_till_done(hass)
    await assert_validation_result(client, {})

    # Valid state in compatible unit - empty response
    hass.states.async_set(
        "sensor.test", 13, attributes={**attributes, **{"unit_of_measurement": unit2}}
    )
    await async_recorder_block_till_done(hass)
    await assert_validation_result(client, {})

    # Valid state, statistic runs again - empty response
    do_adhoc_statistics(hass, start=now + timedelta(hours=2))
    await async_recorder_block_till_done(hass)
    await assert_validation_result(client, {})

    # Remove the state - expect error about missing state
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
    ("units", "attributes", "unit"),
    [
        (US_CUSTOMARY_SYSTEM, POWER_SENSOR_ATTRIBUTES, "W"),
    ],
)
async def test_validate_statistics_unsupported_state_class(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    units,
    attributes,
    unit,
) -> None:
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
    ("units", "attributes", "unit"),
    [
        (US_CUSTOMARY_SYSTEM, POWER_SENSOR_ATTRIBUTES, "W"),
    ],
)
async def test_validate_statistics_sensor_no_longer_recorded(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    units,
    attributes,
    unit,
) -> None:
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
    instance = get_instance(hass)
    with patch.object(
        instance,
        "entity_filter",
        return_value=False,
    ):
        await assert_validation_result(client, expected)


@pytest.mark.parametrize(
    ("units", "attributes", "unit"),
    [
        (US_CUSTOMARY_SYSTEM, POWER_SENSOR_ATTRIBUTES, "W"),
    ],
)
async def test_validate_statistics_sensor_not_recorded(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    units,
    attributes,
    unit,
) -> None:
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
    instance = get_instance(hass)
    with patch.object(
        instance,
        "entity_filter",
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
    ("units", "attributes", "unit"),
    [
        (US_CUSTOMARY_SYSTEM, POWER_SENSOR_ATTRIBUTES, "W"),
    ],
)
async def test_validate_statistics_sensor_removed(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    units,
    attributes,
    unit,
) -> None:
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
    ("attributes", "unit1", "unit2"),
    [
        (BATTERY_SENSOR_ATTRIBUTES, "cats", "dogs"),
        (NONE_SENSOR_ATTRIBUTES, "cats", "dogs"),
    ],
)
async def test_validate_statistics_unit_change_no_conversion(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    attributes,
    unit1,
    unit2,
) -> None:
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
        with session_scope(hass=hass, read_only=True) as session:
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
    hass.states.async_set(
        "sensor.test", 10, attributes={**attributes, **{"unit_of_measurement": unit1}}
    )
    await assert_validation_result(client, {})

    # No statistics, changed unit - empty response
    hass.states.async_set(
        "sensor.test", 11, attributes={**attributes, **{"unit_of_measurement": unit2}}
    )
    await assert_validation_result(client, {})

    # Run statistics, no statistics will be generated because of conflicting units
    await async_recorder_block_till_done(hass)
    do_adhoc_statistics(hass, start=now)
    await async_recorder_block_till_done(hass)
    await assert_statistic_ids([])

    # No statistics, original unit - empty response
    hass.states.async_set(
        "sensor.test", 12, attributes={**attributes, **{"unit_of_measurement": unit1}}
    )
    await assert_validation_result(client, {})

    # Run statistics one hour later, only the state with unit1 will be considered
    await async_recorder_block_till_done(hass)
    do_adhoc_statistics(hass, start=now + timedelta(hours=1))
    await async_recorder_block_till_done(hass)
    await assert_statistic_ids(
        [{"statistic_id": "sensor.test", "unit_of_measurement": unit1}]
    )
    await assert_validation_result(client, {})

    # Change unit - expect error
    hass.states.async_set(
        "sensor.test", 13, attributes={**attributes, **{"unit_of_measurement": unit2}}
    )
    await async_recorder_block_till_done(hass)
    expected = {
        "sensor.test": [
            {
                "data": {
                    "metadata_unit": unit1,
                    "state_unit": unit2,
                    "statistic_id": "sensor.test",
                    "supported_unit": unit1,
                },
                "type": "units_changed",
            }
        ],
    }
    await assert_validation_result(client, expected)

    # Original unit - empty response
    hass.states.async_set(
        "sensor.test", 14, attributes={**attributes, **{"unit_of_measurement": unit1}}
    )
    await async_recorder_block_till_done(hass)
    await assert_validation_result(client, {})

    # Valid state, statistic runs again - empty response
    await async_recorder_block_till_done(hass)
    do_adhoc_statistics(hass, start=now + timedelta(hours=2))
    await async_recorder_block_till_done(hass)
    await assert_validation_result(client, {})

    # Remove the state - expect error
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
    ("attributes", "unit1", "unit2"),
    [
        (NONE_SENSOR_ATTRIBUTES, "m3", "m³"),
        (NONE_SENSOR_ATTRIBUTES, "rpm", "RPM"),
        (NONE_SENSOR_ATTRIBUTES, "RPM", "rpm"),
    ],
)
async def test_validate_statistics_unit_change_equivalent_units(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    attributes,
    unit1,
    unit2,
) -> None:
    """Test validate_statistics.

    This tests no validation issue is created when a sensor's unit changes to an
    equivalent unit.
    """
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
        with session_scope(hass=hass, read_only=True) as session:
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
    hass.states.async_set(
        "sensor.test", 10, attributes={**attributes, **{"unit_of_measurement": unit1}}
    )
    await assert_validation_result(client, {})

    # Run statistics
    await async_recorder_block_till_done(hass)
    do_adhoc_statistics(hass, start=now)
    await async_recorder_block_till_done(hass)
    await assert_statistic_ids(
        [{"statistic_id": "sensor.test", "unit_of_measurement": unit1}]
    )

    # Units changed to an equivalent unit - empty response
    hass.states.async_set(
        "sensor.test", 12, attributes={**attributes, **{"unit_of_measurement": unit2}}
    )
    await assert_validation_result(client, {})

    # Run statistics one hour later, metadata will be updated
    await async_recorder_block_till_done(hass)
    do_adhoc_statistics(hass, start=now + timedelta(hours=1))
    await async_recorder_block_till_done(hass)
    await assert_statistic_ids(
        [{"statistic_id": "sensor.test", "unit_of_measurement": unit2}]
    )
    await assert_validation_result(client, {})


@pytest.mark.parametrize(
    ("attributes", "unit1", "unit2", "supported_unit"),
    [
        (NONE_SENSOR_ATTRIBUTES, "m³", "m3", "CCF, L, fl. oz., ft³, gal, mL, m³"),
    ],
)
async def test_validate_statistics_unit_change_equivalent_units_2(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    attributes,
    unit1,
    unit2,
    supported_unit,
) -> None:
    """Test validate_statistics.

    This tests a validation issue is created when a sensor's unit changes to an
    equivalent unit which is not known to the unit converters.
    """

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
        with session_scope(hass=hass, read_only=True) as session:
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
    hass.states.async_set(
        "sensor.test", 10, attributes={**attributes, **{"unit_of_measurement": unit1}}
    )
    await assert_validation_result(client, {})

    # Run statistics
    await async_recorder_block_till_done(hass)
    do_adhoc_statistics(hass, start=now)
    await async_recorder_block_till_done(hass)
    await assert_statistic_ids(
        [{"statistic_id": "sensor.test", "unit_of_measurement": unit1}]
    )

    # Units changed to an equivalent unit which is not known by the unit converters
    hass.states.async_set(
        "sensor.test", 12, attributes={**attributes, **{"unit_of_measurement": unit2}}
    )
    expected = {
        "sensor.test": [
            {
                "data": {
                    "metadata_unit": unit1,
                    "state_unit": unit2,
                    "statistic_id": "sensor.test",
                    "supported_unit": supported_unit,
                },
                "type": "units_changed",
            }
        ],
    }
    await assert_validation_result(client, expected)

    # Run statistics one hour later, metadata will not be updated
    await async_recorder_block_till_done(hass)
    do_adhoc_statistics(hass, start=now + timedelta(hours=1))
    await async_recorder_block_till_done(hass)
    await assert_statistic_ids(
        [{"statistic_id": "sensor.test", "unit_of_measurement": unit1}]
    )
    await assert_validation_result(client, expected)


async def test_validate_statistics_other_domain(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test sensor does not raise issues for statistics for other domains."""
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

    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)
    client = await hass_ws_client()

    # Create statistics for another domain
    metadata: StatisticMetaData = {
        "has_mean": True,
        "has_sum": True,
        "name": None,
        "source": RECORDER_DOMAIN,
        "statistic_id": "number.test",
        "unit_of_measurement": None,
    }
    statistics: StatisticData = {
        "last_reset": None,
        "max": None,
        "mean": None,
        "min": None,
        "start": datetime(2020, 10, 6, tzinfo=dt_util.UTC),
        "state": None,
        "sum": None,
    }
    async_import_statistics(hass, metadata, (statistics,))
    await async_recorder_block_till_done(hass)

    # We should not get complains about the missing number entity
    await assert_validation_result(client, {})


def record_meter_states(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    zero: datetime,
    entity_id: str,
    _attributes,
    seq,
):
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
    freezer.move_to(zero)

    states[entity_id].append(set_state(entity_id, seq[0], attributes=attributes))

    freezer.move_to(one)
    states[entity_id].append(set_state(entity_id, seq[1], attributes=attributes))

    freezer.move_to(two)
    states[entity_id].append(set_state(entity_id, seq[2], attributes=attributes))

    freezer.move_to(three)
    states[entity_id].append(set_state(entity_id, seq[3], attributes=attributes))

    attributes = dict(_attributes)
    if "last_reset" in _attributes:
        attributes["last_reset"] = four.isoformat()

    freezer.move_to(four)
    states[entity_id].append(set_state(entity_id, seq[4], attributes=attributes))

    freezer.move_to(five)
    states[entity_id].append(set_state(entity_id, seq[5], attributes=attributes))

    freezer.move_to(six)
    states[entity_id].append(set_state(entity_id, seq[6], attributes=attributes))

    freezer.move_to(seven)
    states[entity_id].append(set_state(entity_id, seq[7], attributes=attributes))

    freezer.move_to(eight)
    states[entity_id].append(set_state(entity_id, seq[8], attributes=attributes))

    return four, eight, states


def record_meter_state(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    zero: datetime,
    entity_id: str,
    attributes,
    seq,
):
    """Record test state.

    We inject a state update for meter sensor.
    """

    def set_state(entity_id, state, **kwargs):
        """Set the state."""
        hass.states.set(entity_id, state, **kwargs)
        wait_recording_done(hass)
        return hass.states.get(entity_id)

    states = {entity_id: []}
    freezer.move_to(zero)
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
    with freeze_time(one) as freezer:
        states[entity_id].append(set_state(entity_id, "10", attributes=attributes))

        freezer.move_to(two)
        states[entity_id].append(set_state(entity_id, "25", attributes=attributes))

        freezer.move_to(three)
        states[entity_id].append(
            set_state(entity_id, STATE_UNAVAILABLE, attributes=attributes)
        )

    return four, states


async def test_exclude_attributes(
    recorder_mock: Recorder, hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Test sensor attributes to be excluded."""
    platform = getattr(hass.components, "test.sensor")
    platform.init(empty=True)
    platform.ENTITIES["0"] = platform.MockSensor(
        has_entity_name=True,
        unique_id="test",
        name="Test",
        native_value="option1",
        device_class=SensorDeviceClass.ENUM,
        options=["option1", "option2"],
    )
    assert await async_setup_component(hass, "sensor", {"sensor": {"platform": "test"}})
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    def _fetch_states() -> list[State]:
        with session_scope(hass=hass, read_only=True) as session:
            native_states = []
            for db_state, db_state_attributes, db_states_meta in (
                session.query(States, StateAttributes, StatesMeta)
                .outerjoin(
                    StateAttributes,
                    States.attributes_id == StateAttributes.attributes_id,
                )
                .outerjoin(StatesMeta, States.metadata_id == StatesMeta.metadata_id)
            ):
                db_state.entity_id = db_states_meta.entity_id
                state = db_state.to_native()
                state.attributes = db_state_attributes.to_native()
                native_states.append(state)
            return native_states

    states: list[State] = await hass.async_add_executor_job(_fetch_states)
    assert len(states) == 1
    assert ATTR_OPTIONS not in states[0].attributes
    assert ATTR_FRIENDLY_NAME in states[0].attributes
