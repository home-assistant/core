"""The test for the data filter sensor platform."""
from datetime import timedelta
from os import path

from pytest import fixture

from homeassistant import config as hass_config
from homeassistant.components.filter.sensor import (
    DOMAIN,
    LowPassFilter,
    OutlierFilter,
    RangeFilter,
    ThrottleFilter,
    TimeSMAFilter,
    TimeThrottleFilter,
)
from homeassistant.components.sensor import DEVICE_CLASS_TEMPERATURE
from homeassistant.const import SERVICE_RELOAD, STATE_UNAVAILABLE, STATE_UNKNOWN
import homeassistant.core as ha
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.async_mock import patch
from tests.common import assert_setup_component, async_init_recorder_component


@fixture
def values():
    """Fixture for a list of test States."""
    values = []
    raw_values = [20, 19, 18, 21, 22, 0]
    timestamp = dt_util.utcnow()
    for val in raw_values:
        values.append(ha.State("sensor.test_monitored", val, last_updated=timestamp))
        timestamp += timedelta(minutes=1)
    return values


async def test_setup_fail(hass):
    """Test if filter doesn't exist."""
    config = {
        "sensor": {
            "platform": "filter",
            "entity_id": "sensor.test_monitored",
            "filters": [{"filter": "nonexisting"}],
        }
    }
    with assert_setup_component(0):
        assert await async_setup_component(hass, "sensor", config)
        await hass.async_block_till_done()


async def test_chain(hass, values):
    """Test if filter chaining works."""
    config = {
        "sensor": {
            "platform": "filter",
            "name": "test",
            "entity_id": "sensor.test_monitored",
            "filters": [
                {"filter": "outlier", "window_size": 10, "radius": 4.0},
                {"filter": "lowpass", "time_constant": 10, "precision": 2},
                {"filter": "throttle", "window_size": 1},
            ],
        }
    }
    await async_init_recorder_component(hass)

    with assert_setup_component(1, "sensor"):
        assert await async_setup_component(hass, "sensor", config)
        await hass.async_block_till_done()

        for value in values:
            hass.states.async_set(config["sensor"]["entity_id"], value.state)
            await hass.async_block_till_done()

        state = hass.states.get("sensor.test")
        assert "18.05" == state.state


async def test_chain_history(hass, values, missing=False):
    """Test if filter chaining works."""
    config = {
        "history": {},
        "sensor": {
            "platform": "filter",
            "name": "test",
            "entity_id": "sensor.test_monitored",
            "filters": [
                {"filter": "outlier", "window_size": 10, "radius": 4.0},
                {"filter": "lowpass", "time_constant": 10, "precision": 2},
                {"filter": "throttle", "window_size": 1},
            ],
        },
    }
    await async_init_recorder_component(hass)
    assert_setup_component(1, "history")

    t_0 = dt_util.utcnow() - timedelta(minutes=1)
    t_1 = dt_util.utcnow() - timedelta(minutes=2)
    t_2 = dt_util.utcnow() - timedelta(minutes=3)
    t_3 = dt_util.utcnow() - timedelta(minutes=4)

    if missing:
        fake_states = {}
    else:
        fake_states = {
            "sensor.test_monitored": [
                ha.State("sensor.test_monitored", 18.0, last_changed=t_0),
                ha.State("sensor.test_monitored", "unknown", last_changed=t_1),
                ha.State("sensor.test_monitored", 19.0, last_changed=t_2),
                ha.State("sensor.test_monitored", 18.2, last_changed=t_3),
            ]
        }

    with patch(
        "homeassistant.components.history.state_changes_during_period",
        return_value=fake_states,
    ):
        with patch(
            "homeassistant.components.history.get_last_state_changes",
            return_value=fake_states,
        ):
            with assert_setup_component(1, "sensor"):
                assert await async_setup_component(hass, "sensor", config)
                await hass.async_block_till_done()

            for value in values:
                hass.states.async_set(config["sensor"]["entity_id"], value.state)
                await hass.async_block_till_done()

            state = hass.states.get("sensor.test")
            if missing:
                assert "18.05" == state.state
            else:
                assert "17.05" == state.state


async def test_source_state_none(hass, values):
    """Test is source sensor state is null and sets state to STATE_UNKNOWN."""
    await async_init_recorder_component(hass)

    config = {
        "sensor": [
            {
                "platform": "template",
                "sensors": {
                    "template_test": {
                        "value_template": "{{ states.sensor.test_state.state }}"
                    }
                },
            },
            {
                "platform": "filter",
                "name": "test",
                "entity_id": "sensor.template_test",
                "filters": [
                    {
                        "filter": "time_simple_moving_average",
                        "window_size": "00:01",
                        "precision": "2",
                    }
                ],
            },
        ]
    }
    await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    hass.states.async_set("sensor.test_state", 0)

    await hass.async_block_till_done()
    state = hass.states.get("sensor.template_test")
    assert state.state == "0"

    await hass.async_block_till_done()
    state = hass.states.get("sensor.test")
    assert state.state == "0.0"

    # Force Template Reload
    yaml_path = path.join(
        _get_fixtures_base_path(),
        "fixtures",
        "template/sensor_configuration.yaml",
    )
    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            "template",
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    # Template state gets to None
    state = hass.states.get("sensor.template_test")
    assert state is None

    # Filter sensor ignores None state setting state to STATE_UNKNOWN
    state = hass.states.get("sensor.test")
    assert state.state == STATE_UNKNOWN


async def test_chain_history_missing(hass, values):
    """Test if filter chaining works when recorder is enabled but the source is not recorded."""
    await test_chain_history(hass, values, missing=True)


async def test_history_time(hass):
    """Test loading from history based on a time window."""
    config = {
        "history": {},
        "sensor": {
            "platform": "filter",
            "name": "test",
            "entity_id": "sensor.test_monitored",
            "filters": [{"filter": "time_throttle", "window_size": "00:01"}],
        },
    }
    await async_init_recorder_component(hass)
    assert_setup_component(1, "history")

    t_0 = dt_util.utcnow() - timedelta(minutes=1)
    t_1 = dt_util.utcnow() - timedelta(minutes=2)
    t_2 = dt_util.utcnow() - timedelta(minutes=3)

    fake_states = {
        "sensor.test_monitored": [
            ha.State("sensor.test_monitored", 18.0, last_changed=t_0),
            ha.State("sensor.test_monitored", 19.0, last_changed=t_1),
            ha.State("sensor.test_monitored", 18.2, last_changed=t_2),
        ]
    }
    with patch(
        "homeassistant.components.history.state_changes_during_period",
        return_value=fake_states,
    ):
        with patch(
            "homeassistant.components.history.get_last_state_changes",
            return_value=fake_states,
        ):
            with assert_setup_component(1, "sensor"):
                assert await async_setup_component(hass, "sensor", config)
                await hass.async_block_till_done()

            await hass.async_block_till_done()
            state = hass.states.get("sensor.test")
            assert "18.0" == state.state


async def test_setup(hass):
    """Test if filter attributes are inherited."""
    config = {
        "sensor": {
            "platform": "filter",
            "name": "test",
            "entity_id": "sensor.test_monitored",
            "filters": [
                {"filter": "outlier", "window_size": 10, "radius": 4.0},
            ],
        }
    }

    await async_init_recorder_component(hass)

    with assert_setup_component(1, "sensor"):
        assert await async_setup_component(hass, "sensor", config)
        await hass.async_block_till_done()

        hass.states.async_set(
            "sensor.test_monitored",
            1,
            {"icon": "mdi:test", "device_class": DEVICE_CLASS_TEMPERATURE},
        )
        await hass.async_block_till_done()
        state = hass.states.get("sensor.test")
        assert state.attributes["icon"] == "mdi:test"
        assert state.attributes["device_class"] == DEVICE_CLASS_TEMPERATURE
        assert state.state == "1.0"


async def test_invalid_state(hass):
    """Test if filter attributes are inherited."""
    config = {
        "sensor": {
            "platform": "filter",
            "name": "test",
            "entity_id": "sensor.test_monitored",
            "filters": [
                {"filter": "outlier", "window_size": 10, "radius": 4.0},
            ],
        }
    }

    await async_init_recorder_component(hass)

    with assert_setup_component(1, "sensor"):
        assert await async_setup_component(hass, "sensor", config)
        await hass.async_block_till_done()

        hass.states.async_set("sensor.test_monitored", STATE_UNAVAILABLE)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.test")
        assert state.state == STATE_UNAVAILABLE

        hass.states.async_set("sensor.test_monitored", "invalid")
        await hass.async_block_till_done()

        state = hass.states.get("sensor.test")
        assert state.state == STATE_UNAVAILABLE


async def test_outlier(values):
    """Test if outlier filter works."""
    filt = OutlierFilter(window_size=3, precision=2, entity=None, radius=4.0)
    for state in values:
        filtered = filt.filter_state(state)
    assert 21 == filtered.state


def test_outlier_step(values):
    """
    Test step-change handling in outlier.

    Test if outlier filter handles long-running step-changes correctly.
    It should converge to no longer filter once just over half the
    window_size is occupied by the new post step-change values.
    """
    filt = OutlierFilter(window_size=3, precision=2, entity=None, radius=1.1)
    values[-1].state = 22
    for state in values:
        filtered = filt.filter_state(state)
    assert 22 == filtered.state


def test_initial_outlier(values):
    """Test issue #13363."""
    filt = OutlierFilter(window_size=3, precision=2, entity=None, radius=4.0)
    out = ha.State("sensor.test_monitored", 4000)
    for state in [out] + values:
        filtered = filt.filter_state(state)
    assert 21 == filtered.state


def test_unknown_state_outlier(values):
    """Test issue #32395."""
    filt = OutlierFilter(window_size=3, precision=2, entity=None, radius=4.0)
    out = ha.State("sensor.test_monitored", "unknown")
    for state in [out] + values + [out]:
        try:
            filtered = filt.filter_state(state)
        except ValueError:
            assert state.state == "unknown"
    assert 21 == filtered.state


def test_precision_zero(values):
    """Test if precision of zero returns an integer."""
    filt = LowPassFilter(window_size=10, precision=0, entity=None, time_constant=10)
    for state in values:
        filtered = filt.filter_state(state)
    assert isinstance(filtered.state, int)


def test_lowpass(values):
    """Test if lowpass filter works."""
    filt = LowPassFilter(window_size=10, precision=2, entity=None, time_constant=10)
    out = ha.State("sensor.test_monitored", "unknown")
    for state in [out] + values + [out]:
        try:
            filtered = filt.filter_state(state)
        except ValueError:
            assert state.state == "unknown"
    assert 18.05 == filtered.state


def test_range(values):
    """Test if range filter works."""
    lower = 10
    upper = 20
    filt = RangeFilter(entity=None, precision=2, lower_bound=lower, upper_bound=upper)
    for unf_state in values:
        unf = float(unf_state.state)
        filtered = filt.filter_state(unf_state)
        if unf < lower:
            assert lower == filtered.state
        elif unf > upper:
            assert upper == filtered.state
        else:
            assert unf == filtered.state


def test_range_zero(values):
    """Test if range filter works with zeroes as bounds."""
    lower = 0
    upper = 0
    filt = RangeFilter(entity=None, precision=2, lower_bound=lower, upper_bound=upper)
    for unf_state in values:
        unf = float(unf_state.state)
        filtered = filt.filter_state(unf_state)
        if unf < lower:
            assert lower == filtered.state
        elif unf > upper:
            assert upper == filtered.state
        else:
            assert unf == filtered.state


def test_throttle(values):
    """Test if lowpass filter works."""
    filt = ThrottleFilter(window_size=3, precision=2, entity=None)
    filtered = []
    for state in values:
        new_state = filt.filter_state(state)
        if not filt.skip_processing:
            filtered.append(new_state)
    assert [20, 21] == [f.state for f in filtered]


def test_time_throttle(values):
    """Test if lowpass filter works."""
    filt = TimeThrottleFilter(
        window_size=timedelta(minutes=2), precision=2, entity=None
    )
    filtered = []
    for state in values:
        new_state = filt.filter_state(state)
        if not filt.skip_processing:
            filtered.append(new_state)
    assert [20, 18, 22] == [f.state for f in filtered]


def test_time_sma(values):
    """Test if time_sma filter works."""
    filt = TimeSMAFilter(
        window_size=timedelta(minutes=2), precision=2, entity=None, type="last"
    )
    for state in values:
        filtered = filt.filter_state(state)
    assert 21.5 == filtered.state


async def test_reload(hass):
    """Verify we can reload filter sensors."""
    await async_init_recorder_component(hass)

    hass.states.async_set("sensor.test_monitored", 12345)
    await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": {
                "platform": "filter",
                "name": "test",
                "entity_id": "sensor.test_monitored",
                "filters": [
                    {"filter": "outlier", "window_size": 10, "radius": 4.0},
                    {"filter": "lowpass", "time_constant": 10, "precision": 2},
                    {"filter": "throttle", "window_size": 1},
                ],
            }
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 2

    assert hass.states.get("sensor.test")

    yaml_path = path.join(
        _get_fixtures_base_path(),
        "fixtures",
        "filter/configuration.yaml",
    )
    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 2

    assert hass.states.get("sensor.test") is None
    assert hass.states.get("sensor.filtered_realistic_humidity")


def _get_fixtures_base_path():
    return path.dirname(path.dirname(path.dirname(__file__)))
