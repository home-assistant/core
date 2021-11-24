"""The test for the statistics sensor platform."""
from datetime import datetime, timedelta
import statistics
import unittest
from unittest.mock import patch

import pytest

from homeassistant import config as hass_config
from homeassistant.components import recorder
from homeassistant.components.sensor import ATTR_STATE_CLASS, STATE_CLASS_MEASUREMENT
from homeassistant.components.statistics.sensor import DOMAIN, StatisticsSensor
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    SERVICE_RELOAD,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    TEMP_CELSIUS,
)
from homeassistant.setup import async_setup_component, setup_component
from homeassistant.util import dt as dt_util

from tests.common import (
    fire_time_changed,
    get_fixture_path,
    get_test_home_assistant,
    init_recorder_component,
)
from tests.components.recorder.common import wait_recording_done


@pytest.fixture(autouse=True)
def mock_legacy_time(legacy_patchable_time):
    """Make time patchable for all the tests."""
    yield


class TestStatisticsSensor(unittest.TestCase):
    """Test the Statistics sensor."""

    def setup_method(self, method):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.values_binary = ["on", "off", "on", "off", "on", "off", "on"]
        self.values = [17, 20, 15.2, 5, 3.8, 9.2, 6.7, 14, 6]
        self.mean = round(sum(self.values) / len(self.values), 2)
        self.addCleanup(self.hass.stop)

    def test_sensor_defaults_binary(self):
        """Test the general behavior of the sensor, with binary source sensor."""
        assert setup_component(
            self.hass,
            "sensor",
            {
                "sensor": [
                    {
                        "platform": "statistics",
                        "name": "test",
                        "entity_id": "binary_sensor.test_monitored",
                    },
                    {
                        "platform": "statistics",
                        "name": "test_unitless",
                        "entity_id": "binary_sensor.test_monitored_unitless",
                    },
                ]
            },
        )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        for value in self.values_binary:
            self.hass.states.set(
                "binary_sensor.test_monitored",
                value,
                {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS},
            )
            self.hass.states.set("binary_sensor.test_monitored_unitless", value)
            self.hass.block_till_done()

        state = self.hass.states.get("sensor.test")
        assert state.state == str(len(self.values_binary))
        assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
        assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_MEASUREMENT
        assert state.attributes.get("buffer_usage_ratio") == round(7 / 20, 2)
        assert state.attributes.get("source_value_valid") is True
        assert "age_coverage_ratio" not in state.attributes

        state = self.hass.states.get("sensor.test_unitless")
        assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None

    def test_sensor_defaults_numeric(self):
        """Test the general behavior of the sensor, with numeric source sensor."""
        assert setup_component(
            self.hass,
            "sensor",
            {
                "sensor": [
                    {
                        "platform": "statistics",
                        "name": "test",
                        "entity_id": "sensor.test_monitored",
                    },
                ]
            },
        )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        for value in self.values:
            self.hass.states.set(
                "sensor.test_monitored",
                value,
                {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS},
            )
            self.hass.block_till_done()

        state = self.hass.states.get("sensor.test")
        assert state.state == str(self.mean)
        assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == TEMP_CELSIUS
        assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_MEASUREMENT
        assert state.attributes.get("buffer_usage_ratio") == round(9 / 20, 2)
        assert state.attributes.get("source_value_valid") is True
        assert "age_coverage_ratio" not in state.attributes

        # Source sensor turns unavailable, then available with valid value,
        # statistics sensor should follow
        state = self.hass.states.get("sensor.test")
        self.hass.states.set(
            "sensor.test_monitored",
            STATE_UNAVAILABLE,
        )
        self.hass.block_till_done()
        new_state = self.hass.states.get("sensor.test")
        assert new_state.state == STATE_UNAVAILABLE
        assert new_state.attributes.get("source_value_valid") is None
        self.hass.states.set(
            "sensor.test_monitored",
            0,
            {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS},
        )
        self.hass.block_till_done()
        new_state = self.hass.states.get("sensor.test")
        new_mean = round(sum(self.values) / (len(self.values) + 1), 2)
        assert new_state.state == str(new_mean)
        assert new_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == TEMP_CELSIUS
        assert new_state.attributes.get("buffer_usage_ratio") == round(10 / 20, 2)
        assert new_state.attributes.get("source_value_valid") is True

        # Source sensor has a nonnumerical state, unit and state should not change
        state = self.hass.states.get("sensor.test")
        self.hass.states.set("sensor.test_monitored", "beer", {})
        self.hass.block_till_done()
        new_state = self.hass.states.get("sensor.test")
        assert new_state.state == str(new_mean)
        assert new_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == TEMP_CELSIUS
        assert new_state.attributes.get("source_value_valid") is False

        # Source sensor has the STATE_UNKNOWN state, unit and state should not change
        state = self.hass.states.get("sensor.test")
        self.hass.states.set("sensor.test_monitored", STATE_UNKNOWN, {})
        self.hass.block_till_done()
        new_state = self.hass.states.get("sensor.test")
        assert new_state.state == str(new_mean)
        assert new_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == TEMP_CELSIUS
        assert new_state.attributes.get("source_value_valid") is False

        # Source sensor is removed, unit and state should not change
        # This is equal to a None value being published
        self.hass.states.remove("sensor.test_monitored")
        self.hass.block_till_done()
        new_state = self.hass.states.get("sensor.test")
        assert new_state.state == str(new_mean)
        assert new_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == TEMP_CELSIUS
        assert new_state.attributes.get("source_value_valid") is False

    def test_sampling_size_non_default(self):
        """Test rotation."""
        assert setup_component(
            self.hass,
            "sensor",
            {
                "sensor": [
                    {
                        "platform": "statistics",
                        "name": "test",
                        "entity_id": "sensor.test_monitored",
                        "sampling_size": 5,
                    },
                ]
            },
        )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        for value in self.values:
            self.hass.states.set(
                "sensor.test_monitored",
                value,
                {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS},
            )
            self.hass.block_till_done()

        state = self.hass.states.get("sensor.test")
        new_mean = round(sum(self.values[-5:]) / len(self.values[-5:]), 2)
        assert state.state == str(new_mean)
        assert state.attributes.get("buffer_usage_ratio") == round(5 / 5, 2)

    def test_sampling_size_1(self):
        """Test validity of stats requiring only one sample."""
        assert setup_component(
            self.hass,
            "sensor",
            {
                "sensor": [
                    {
                        "platform": "statistics",
                        "name": "test",
                        "entity_id": "sensor.test_monitored",
                        "sampling_size": 1,
                    },
                ]
            },
        )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        for value in self.values[-3:]:  # just the last 3 will do
            self.hass.states.set(
                "sensor.test_monitored",
                value,
                {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS},
            )
            self.hass.block_till_done()

        state = self.hass.states.get("sensor.test")
        new_mean = float(self.values[-1])
        assert state.state == str(new_mean)
        assert state.attributes.get("buffer_usage_ratio") == round(1 / 1, 2)

    def test_age_limit_expiry(self):
        """Test that values are removed after certain age."""
        now = dt_util.utcnow()
        mock_data = {
            "return_time": datetime(now.year + 1, 8, 2, 12, 23, tzinfo=dt_util.UTC)
        }

        def mock_now():
            return mock_data["return_time"]

        with patch(
            "homeassistant.components.statistics.sensor.dt_util.utcnow", new=mock_now
        ):
            assert setup_component(
                self.hass,
                "sensor",
                {
                    "sensor": [
                        {
                            "platform": "statistics",
                            "name": "test",
                            "entity_id": "sensor.test_monitored",
                            "max_age": {"minutes": 4},
                        },
                    ]
                },
            )

            self.hass.block_till_done()
            self.hass.start()
            self.hass.block_till_done()

            for value in self.values:
                self.hass.states.set(
                    "sensor.test_monitored",
                    value,
                    {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS},
                )
                self.hass.block_till_done()
                mock_data["return_time"] += timedelta(minutes=1)

            # After adding all values, we should only see 5 values in memory

            state = self.hass.states.get("sensor.test")
            new_mean = round(sum(self.values[-5:]) / len(self.values[-5:]), 2)
            assert state.state == str(new_mean)
            assert state.attributes.get("buffer_usage_ratio") == round(5 / 20, 2)
            assert state.attributes.get("age_coverage_ratio") == 1.0

            # Values expire over time. Only two are left

            mock_data["return_time"] += timedelta(minutes=2)
            fire_time_changed(self.hass, mock_data["return_time"])
            self.hass.block_till_done()

            state = self.hass.states.get("sensor.test")
            new_mean = round(sum(self.values[-2:]) / len(self.values[-2:]), 2)
            assert state.state == str(new_mean)
            assert state.attributes.get("buffer_usage_ratio") == round(2 / 20, 2)
            assert state.attributes.get("age_coverage_ratio") == 1 / 4

            # Values expire over time. Only one is left

            mock_data["return_time"] += timedelta(minutes=1)
            fire_time_changed(self.hass, mock_data["return_time"])
            self.hass.block_till_done()

            state = self.hass.states.get("sensor.test")
            new_mean = float(self.values[-1])
            assert state.state == str(new_mean)
            assert state.attributes.get("buffer_usage_ratio") == round(1 / 20, 2)
            assert state.attributes.get("age_coverage_ratio") == 0

            # Values expire over time. Memory is empty

            mock_data["return_time"] += timedelta(minutes=1)
            fire_time_changed(self.hass, mock_data["return_time"])
            self.hass.block_till_done()

            state = self.hass.states.get("sensor.test")
            assert state.state == STATE_UNKNOWN
            assert state.attributes.get("buffer_usage_ratio") == round(0 / 20, 2)
            assert state.attributes.get("age_coverage_ratio") == STATE_UNKNOWN

    def test_precision_0(self):
        """Test correct result with precision=0 as integer."""
        assert setup_component(
            self.hass,
            "sensor",
            {
                "sensor": [
                    {
                        "platform": "statistics",
                        "name": "test",
                        "entity_id": "sensor.test_monitored",
                        "precision": 0,
                    },
                ]
            },
        )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        for value in self.values:
            self.hass.states.set(
                "sensor.test_monitored",
                value,
                {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS},
            )
            self.hass.block_till_done()

        state = self.hass.states.get("sensor.test")
        assert state.state == str(int(round(self.mean)))

    def test_precision_1(self):
        """Test correct result with precision=1 rounded to one decimal."""
        assert setup_component(
            self.hass,
            "sensor",
            {
                "sensor": [
                    {
                        "platform": "statistics",
                        "name": "test",
                        "entity_id": "sensor.test_monitored",
                        "precision": 1,
                    },
                ]
            },
        )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        for value in self.values:
            self.hass.states.set(
                "sensor.test_monitored",
                value,
                {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS},
            )
            self.hass.block_till_done()

        state = self.hass.states.get("sensor.test")
        assert state.state == str(round(sum(self.values) / len(self.values), 1))

    def test_state_class(self):
        """Test state class, which depends on the characteristic configured."""
        assert setup_component(
            self.hass,
            "sensor",
            {
                "sensor": [
                    {
                        "platform": "statistics",
                        "name": "test_normal",
                        "entity_id": "sensor.test_monitored",
                        "state_characteristic": "count",
                    },
                    {
                        "platform": "statistics",
                        "name": "test_nan",
                        "entity_id": "sensor.test_monitored",
                        "state_characteristic": "datetime_oldest",
                    },
                ]
            },
        )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        for value in self.values:
            self.hass.states.set(
                "sensor.test_monitored",
                value,
                {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS},
            )
            self.hass.block_till_done()

        state = self.hass.states.get("sensor.test_normal")
        assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_MEASUREMENT
        state = self.hass.states.get("sensor.test_nan")
        assert state.attributes.get(ATTR_STATE_CLASS) is None

    def test_unitless_source_sensor(self):
        """Statistics for a unitless source sensor should never have a unit."""
        assert setup_component(
            self.hass,
            "sensor",
            {
                "sensor": [
                    {
                        "platform": "statistics",
                        "name": "test_unitless_1",
                        "entity_id": "sensor.test_monitored_unitless",
                        "state_characteristic": "count",
                    },
                    {
                        "platform": "statistics",
                        "name": "test_unitless_2",
                        "entity_id": "sensor.test_monitored_unitless",
                        "state_characteristic": "mean",
                    },
                    {
                        "platform": "statistics",
                        "name": "test_unitless_3",
                        "entity_id": "sensor.test_monitored_unitless",
                        "state_characteristic": "change_second",
                    },
                ]
            },
        )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        for value in self.values:
            self.hass.states.set(
                "sensor.test_monitored_unitless",
                value,
            )
            self.hass.block_till_done()

        state = self.hass.states.get("sensor.test_unitless_1")
        assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
        state = self.hass.states.get("sensor.test_unitless_2")
        assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
        state = self.hass.states.get("sensor.test_unitless_3")
        assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None

    def test_state_characteristics(self):
        """Test configured state characteristic for value and unit."""
        now = dt_util.utcnow()
        mock_data = {
            "return_time": datetime(now.year + 1, 8, 2, 12, 23, 42, tzinfo=dt_util.UTC)
        }

        def mock_now():
            return mock_data["return_time"]

        value_spacing_minutes = 1

        characteristics = (
            {
                "name": "average_linear",
                "value_0": STATE_UNKNOWN,
                "value_1": STATE_UNKNOWN,
                "value_9": 10.68,
                "unit": "°C",
            },
            {
                "name": "average_step",
                "value_0": STATE_UNKNOWN,
                "value_1": STATE_UNKNOWN,
                "value_9": 11.36,
                "unit": "°C",
            },
            {
                "name": "average_timeless",
                "value_0": STATE_UNKNOWN,
                "value_1": float(self.values[0]),
                "value_9": float(self.mean),
                "unit": "°C",
            },
            {
                "name": "change",
                "value_0": STATE_UNKNOWN,
                "value_1": float(0),
                "value_9": float(round(self.values[-1] - self.values[0], 2)),
                "unit": "°C",
            },
            {
                "name": "change_sample",
                "value_0": STATE_UNKNOWN,
                "value_1": STATE_UNKNOWN,
                "value_9": float(
                    round(
                        (self.values[-1] - self.values[0]) / (len(self.values) - 1), 2
                    )
                ),
                "unit": "°C/sample",
            },
            {
                "name": "change_second",
                "value_0": STATE_UNKNOWN,
                "value_1": STATE_UNKNOWN,
                "value_9": float(
                    round(
                        (self.values[-1] - self.values[0])
                        / (60 * (len(self.values) - 1)),
                        2,
                    )
                ),
                "unit": "°C/s",
            },
            {
                "name": "count",
                "value_0": 0,
                "value_1": 1,
                "value_9": len(self.values),
                "unit": None,
            },
            {
                "name": "datetime_newest",
                "value_0": STATE_UNKNOWN,
                "value_1": datetime(
                    now.year + 1,
                    8,
                    2,
                    12,
                    23 + len(self.values) + 10,
                    42,
                    tzinfo=dt_util.UTC,
                ),
                "value_9": datetime(
                    now.year + 1,
                    8,
                    2,
                    12,
                    23 + len(self.values) - 1,
                    42,
                    tzinfo=dt_util.UTC,
                ),
                "unit": None,
            },
            {
                "name": "datetime_oldest",
                "value_0": STATE_UNKNOWN,
                "value_1": datetime(
                    now.year + 1,
                    8,
                    2,
                    12,
                    23 + len(self.values) + 10,
                    42,
                    tzinfo=dt_util.UTC,
                ),
                "value_9": datetime(now.year + 1, 8, 2, 12, 23, 42, tzinfo=dt_util.UTC),
                "unit": None,
            },
            {
                "name": "distance_95_percent_of_values",
                "value_0": STATE_UNKNOWN,
                "value_1": STATE_UNKNOWN,
                "value_9": float(round(2 * 1.96 * statistics.stdev(self.values), 2)),
                "unit": "°C",
            },
            {
                "name": "distance_99_percent_of_values",
                "value_0": STATE_UNKNOWN,
                "value_1": STATE_UNKNOWN,
                "value_9": float(round(2 * 2.58 * statistics.stdev(self.values), 2)),
                "unit": "°C",
            },
            {
                "name": "distance_absolute",
                "value_0": STATE_UNKNOWN,
                "value_1": float(0),
                "value_9": float(max(self.values) - min(self.values)),
                "unit": "°C",
            },
            {
                "name": "mean",
                "value_0": STATE_UNKNOWN,
                "value_1": float(self.values[0]),
                "value_9": float(self.mean),
                "unit": "°C",
            },
            {
                "name": "median",
                "value_0": STATE_UNKNOWN,
                "value_1": float(self.values[0]),
                "value_9": float(round(statistics.median(self.values), 2)),
                "unit": "°C",
            },
            {
                "name": "noisiness",
                "value_0": STATE_UNKNOWN,
                "value_1": STATE_UNKNOWN,
                "value_9": float(
                    round(sum([3, 4.8, 10.2, 1.2, 5.4, 2.5, 7.3, 8]) / 8, 2)
                ),
                "unit": "°C",
            },
            {
                "name": "quantiles",
                "value_0": STATE_UNKNOWN,
                "value_1": STATE_UNKNOWN,
                "value_9": [
                    round(quantile, 2) for quantile in statistics.quantiles(self.values)
                ],
                "unit": None,
            },
            {
                "name": "standard_deviation",
                "value_0": STATE_UNKNOWN,
                "value_1": STATE_UNKNOWN,
                "value_9": float(round(statistics.stdev(self.values), 2)),
                "unit": "°C",
            },
            {
                "name": "total",
                "value_0": STATE_UNKNOWN,
                "value_1": float(self.values[0]),
                "value_9": float(sum(self.values)),
                "unit": "°C",
            },
            {
                "name": "value_max",
                "value_0": STATE_UNKNOWN,
                "value_1": float(self.values[0]),
                "value_9": float(max(self.values)),
                "unit": "°C",
            },
            {
                "name": "value_min",
                "value_0": STATE_UNKNOWN,
                "value_1": float(self.values[0]),
                "value_9": float(min(self.values)),
                "unit": "°C",
            },
            {
                "name": "variance",
                "value_0": STATE_UNKNOWN,
                "value_1": STATE_UNKNOWN,
                "value_9": float(round(statistics.variance(self.values), 2)),
                "unit": "°C²",
            },
        )
        sensors_config = []
        for characteristic in characteristics:
            sensors_config.append(
                {
                    "platform": "statistics",
                    "name": "test_" + characteristic["name"],
                    "entity_id": "sensor.test_monitored",
                    "state_characteristic": characteristic["name"],
                    "max_age": {"minutes": 10},
                }
            )

        with patch(
            "homeassistant.components.statistics.sensor.dt_util.utcnow", new=mock_now
        ):
            assert setup_component(
                self.hass,
                "sensor",
                {"sensor": sensors_config},
            )

            self.hass.block_till_done()
            self.hass.start()
            self.hass.block_till_done()

            # With all values in buffer

            for value in self.values:
                self.hass.states.set(
                    "sensor.test_monitored",
                    value,
                    {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS},
                )
                self.hass.block_till_done()
                mock_data["return_time"] += timedelta(minutes=value_spacing_minutes)

            for characteristic in characteristics:
                state = self.hass.states.get("sensor.test_" + characteristic["name"])
                assert state.state == str(characteristic["value_9"]), (
                    f"value mismatch for characteristic '{characteristic['name']}' (buffer filled) "
                    f"- assert {state.state} == {str(characteristic['value_9'])}"
                )
                assert (
                    state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
                    == characteristic["unit"]
                ), f"unit mismatch for characteristic '{characteristic['name']}'"

            # With empty buffer

            mock_data["return_time"] += timedelta(minutes=10)
            fire_time_changed(self.hass, mock_data["return_time"])
            self.hass.block_till_done()

            for characteristic in characteristics:
                state = self.hass.states.get("sensor.test_" + characteristic["name"])
                assert state.state == str(characteristic["value_0"]), (
                    f"value mismatch for characteristic '{characteristic['name']}' (buffer empty) "
                    f"- assert {state.state} == {str(characteristic['value_0'])}"
                )

            # With single value in buffer

            self.hass.states.set(
                "sensor.test_monitored",
                self.values[0],
                {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS},
            )
            self.hass.block_till_done()
            mock_data["return_time"] += timedelta(minutes=1)

            for characteristic in characteristics:
                state = self.hass.states.get("sensor.test_" + characteristic["name"])
                assert state.state == str(characteristic["value_1"]), (
                    f"value mismatch for characteristic '{characteristic['name']}' (one stored value) "
                    f"- assert {state.state} == {str(characteristic['value_1'])}"
                )

    def test_initialize_from_database(self):
        """Test initializing the statistics from the database."""
        # enable the recorder
        init_recorder_component(self.hass)
        self.hass.block_till_done()
        self.hass.data[recorder.DATA_INSTANCE].block_till_done()
        # store some values
        for value in self.values:
            self.hass.states.set(
                "sensor.test_monitored",
                value,
                {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS},
            )
            self.hass.block_till_done()
        # wait for the recorder to really store the data
        wait_recording_done(self.hass)
        # only now create the statistics component, so that it must read the
        # data from the database
        assert setup_component(
            self.hass,
            "sensor",
            {
                "sensor": [
                    {
                        "platform": "statistics",
                        "name": "test",
                        "entity_id": "sensor.test_monitored",
                        "sampling_size": 100,
                    },
                ]
            },
        )

        self.hass.block_till_done()
        self.hass.start()
        self.hass.block_till_done()

        # check if the result is as in test_sensor_source()
        state = self.hass.states.get("sensor.test")
        assert str(self.mean) == state.state
        assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == TEMP_CELSIUS

    def test_initialize_from_database_with_maxage(self):
        """Test initializing the statistics from the database."""
        now = dt_util.utcnow()
        mock_data = {
            "return_time": datetime(now.year + 1, 8, 2, 12, 23, 42, tzinfo=dt_util.UTC)
        }

        def mock_now():
            return mock_data["return_time"]

        # Testing correct retrieval from recorder, thus we do not
        # want purging to occur within the class itself.
        def mock_purge(self):
            return

        # enable the recorder
        init_recorder_component(self.hass)
        self.hass.block_till_done()
        self.hass.data[recorder.DATA_INSTANCE].block_till_done()

        with patch(
            "homeassistant.components.statistics.sensor.dt_util.utcnow", new=mock_now
        ), patch.object(StatisticsSensor, "_purge_old", mock_purge):
            # store some values
            for value in self.values:
                self.hass.states.set(
                    "sensor.test_monitored",
                    value,
                    {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS},
                )
                self.hass.block_till_done()
                # insert the next value 1 hour later
                mock_data["return_time"] += timedelta(hours=1)

            # wait for the recorder to really store the data
            wait_recording_done(self.hass)
            # only now create the statistics component, so that it must read
            # the data from the database
            assert setup_component(
                self.hass,
                "sensor",
                {
                    "sensor": [
                        {
                            "platform": "statistics",
                            "name": "test",
                            "entity_id": "sensor.test_monitored",
                            "sampling_size": 100,
                            "state_characteristic": "datetime_newest",
                            "max_age": {"hours": 3},
                        },
                    ]
                },
            )
            self.hass.block_till_done()

            self.hass.block_till_done()
            self.hass.start()
            self.hass.block_till_done()

            # check if the result is as in test_sensor_source()
            state = self.hass.states.get("sensor.test")

        assert state.attributes.get("age_coverage_ratio") == round(2 / 3, 2)
        # The max_age timestamp should be 1 hour before what we have right
        # now in mock_data['return_time'].
        assert mock_data["return_time"] == datetime.strptime(
            state.state, "%Y-%m-%d %H:%M:%S%z"
        ) + timedelta(hours=1)


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
            "sensor": [
                {
                    "platform": "statistics",
                    "name": "test",
                    "entity_id": "sensor.test_monitored",
                    "sampling_size": 100,
                },
            ]
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 2

    assert hass.states.get("sensor.test")

    yaml_path = get_fixture_path("configuration.yaml", "statistics")
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
    assert hass.states.get("sensor.cputest")
