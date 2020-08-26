"""The test for the data filter sensor platform."""
from datetime import timedelta
from os import path
import unittest

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
from homeassistant.const import SERVICE_RELOAD
import homeassistant.core as ha
from homeassistant.setup import async_setup_component, setup_component
import homeassistant.util.dt as dt_util

from tests.async_mock import patch
from tests.common import (
    assert_setup_component,
    get_test_home_assistant,
    init_recorder_component,
)


class TestFilterSensor(unittest.TestCase):
    """Test the Data Filter sensor."""

    def setup_method(self, method):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.config.components.add("history")
        raw_values = [20, 19, 18, 21, 22, 0]
        self.values = []

        timestamp = dt_util.utcnow()
        for val in raw_values:
            self.values.append(
                ha.State("sensor.test_monitored", val, last_updated=timestamp)
            )
            timestamp += timedelta(minutes=1)

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def init_recorder(self):
        """Initialize the recorder."""
        init_recorder_component(self.hass)
        self.hass.start()

    def test_setup_fail(self):
        """Test if filter doesn't exist."""
        config = {
            "sensor": {
                "platform": "filter",
                "entity_id": "sensor.test_monitored",
                "filters": [{"filter": "nonexisting"}],
            }
        }
        with assert_setup_component(0):
            assert setup_component(self.hass, "sensor", config)
            self.hass.block_till_done()

    def test_chain(self):
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

        with assert_setup_component(1, "sensor"):
            assert setup_component(self.hass, "sensor", config)
            self.hass.block_till_done()

            for value in self.values:
                self.hass.states.set(config["sensor"]["entity_id"], value.state)
                self.hass.block_till_done()

            state = self.hass.states.get("sensor.test")
            assert "18.05" == state.state

    def test_chain_history(self, missing=False):
        """Test if filter chaining works."""
        self.init_recorder()
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
                    assert setup_component(self.hass, "sensor", config)
                    self.hass.block_till_done()

                for value in self.values:
                    self.hass.states.set(config["sensor"]["entity_id"], value.state)
                    self.hass.block_till_done()

                state = self.hass.states.get("sensor.test")
                if missing:
                    assert "18.05" == state.state
                else:
                    assert "17.05" == state.state

    def test_chain_history_missing(self):
        """Test if filter chaining works when recorder is enabled but the source is not recorded."""
        return self.test_chain_history(missing=True)

    def test_history_time(self):
        """Test loading from history based on a time window."""
        self.init_recorder()
        config = {
            "history": {},
            "sensor": {
                "platform": "filter",
                "name": "test",
                "entity_id": "sensor.test_monitored",
                "filters": [{"filter": "time_throttle", "window_size": "00:01"}],
            },
        }
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
                    assert setup_component(self.hass, "sensor", config)
                    self.hass.block_till_done()

                self.hass.block_till_done()
                state = self.hass.states.get("sensor.test")
                assert "18.0" == state.state

    def test_outlier(self):
        """Test if outlier filter works."""
        filt = OutlierFilter(window_size=3, precision=2, entity=None, radius=4.0)
        for state in self.values:
            filtered = filt.filter_state(state)
        assert 21 == filtered.state

    def test_outlier_step(self):
        """
        Test step-change handling in outlier.

        Test if outlier filter handles long-running step-changes correctly.
        It should converge to no longer filter once just over half the
        window_size is occupied by the new post step-change values.
        """
        filt = OutlierFilter(window_size=3, precision=2, entity=None, radius=1.1)
        self.values[-1].state = 22
        for state in self.values:
            filtered = filt.filter_state(state)
        assert 22 == filtered.state

    def test_initial_outlier(self):
        """Test issue #13363."""
        filt = OutlierFilter(window_size=3, precision=2, entity=None, radius=4.0)
        out = ha.State("sensor.test_monitored", 4000)
        for state in [out] + self.values:
            filtered = filt.filter_state(state)
        assert 21 == filtered.state

    def test_unknown_state_outlier(self):
        """Test issue #32395."""
        filt = OutlierFilter(window_size=3, precision=2, entity=None, radius=4.0)
        out = ha.State("sensor.test_monitored", "unknown")
        for state in [out] + self.values + [out]:
            try:
                filtered = filt.filter_state(state)
            except ValueError:
                assert state.state == "unknown"
        assert 21 == filtered.state

    def test_precision_zero(self):
        """Test if precision of zero returns an integer."""
        filt = LowPassFilter(window_size=10, precision=0, entity=None, time_constant=10)
        for state in self.values:
            filtered = filt.filter_state(state)
        assert isinstance(filtered.state, int)

    def test_lowpass(self):
        """Test if lowpass filter works."""
        filt = LowPassFilter(window_size=10, precision=2, entity=None, time_constant=10)
        out = ha.State("sensor.test_monitored", "unknown")
        for state in [out] + self.values + [out]:
            try:
                filtered = filt.filter_state(state)
            except ValueError:
                assert state.state == "unknown"
        assert 18.05 == filtered.state

    def test_range(self):
        """Test if range filter works."""
        lower = 10
        upper = 20
        filt = RangeFilter(
            entity=None, precision=2, lower_bound=lower, upper_bound=upper
        )
        for unf_state in self.values:
            unf = float(unf_state.state)
            filtered = filt.filter_state(unf_state)
            if unf < lower:
                assert lower == filtered.state
            elif unf > upper:
                assert upper == filtered.state
            else:
                assert unf == filtered.state

    def test_range_zero(self):
        """Test if range filter works with zeroes as bounds."""
        lower = 0
        upper = 0
        filt = RangeFilter(
            entity=None, precision=2, lower_bound=lower, upper_bound=upper
        )
        for unf_state in self.values:
            unf = float(unf_state.state)
            filtered = filt.filter_state(unf_state)
            if unf < lower:
                assert lower == filtered.state
            elif unf > upper:
                assert upper == filtered.state
            else:
                assert unf == filtered.state

    def test_throttle(self):
        """Test if lowpass filter works."""
        filt = ThrottleFilter(window_size=3, precision=2, entity=None)
        filtered = []
        for state in self.values:
            new_state = filt.filter_state(state)
            if not filt.skip_processing:
                filtered.append(new_state)
        assert [20, 21] == [f.state for f in filtered]

    def test_time_throttle(self):
        """Test if lowpass filter works."""
        filt = TimeThrottleFilter(
            window_size=timedelta(minutes=2), precision=2, entity=None
        )
        filtered = []
        for state in self.values:
            new_state = filt.filter_state(state)
            if not filt.skip_processing:
                filtered.append(new_state)
        assert [20, 18, 22] == [f.state for f in filtered]

    def test_time_sma(self):
        """Test if time_sma filter works."""
        filt = TimeSMAFilter(
            window_size=timedelta(minutes=2), precision=2, entity=None, type="last"
        )
        for state in self.values:
            filtered = filt.filter_state(state)
        assert 21.5 == filtered.state


async def test_reload(hass):
    """Verify we can reload filter sensors."""
    await hass.async_add_executor_job(
        init_recorder_component, hass
    )  # force in memory db

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
        _get_fixtures_base_path(), "fixtures", "filter/configuration.yaml",
    )
    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            DOMAIN, SERVICE_RELOAD, {}, blocking=True,
        )
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 2

    assert hass.states.get("sensor.test") is None
    assert hass.states.get("sensor.filtered_realistic_humidity")


def _get_fixtures_base_path():
    return path.dirname(path.dirname(path.dirname(__file__)))
