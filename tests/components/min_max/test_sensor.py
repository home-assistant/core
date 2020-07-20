"""The test for the min/max sensor platform."""
import statistics
import unittest

from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    UNIT_PERCENTAGE,
)
from homeassistant.setup import setup_component

from tests.common import get_test_home_assistant


class TestMinMaxSensor(unittest.TestCase):
    """Test the min/max sensor."""

    def setup_method(self, method):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.values = [17, 20, 15.3]
        self.count = len(self.values)
        self.min = min(self.values)
        self.max = max(self.values)
        self.mean = round(sum(self.values) / self.count, 2)
        self.mean_1_digit = round(sum(self.values) / self.count, 1)
        self.mean_4_digits = round(sum(self.values) / self.count, 4)
        self.median = round(statistics.median(self.values), 2)

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_min_sensor(self):
        """Test the min sensor."""
        config = {
            "sensor": {
                "platform": "min_max",
                "name": "test_min",
                "type": "min",
                "entity_ids": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
            }
        }

        assert setup_component(self.hass, "sensor", config)

        entity_ids = config["sensor"]["entity_ids"]

        for entity_id, value in dict(zip(entity_ids, self.values)).items():
            self.hass.states.set(entity_id, value)
            self.hass.block_till_done()

        state = self.hass.states.get("sensor.test_min")

        assert str(float(self.min)) == state.state
        assert entity_ids[2] == state.attributes.get("min_entity_id")
        assert self.max == state.attributes.get("max_value")
        assert entity_ids[1] == state.attributes.get("max_entity_id")
        assert self.mean == state.attributes.get("mean")
        assert self.median == state.attributes.get("median")

    def test_max_sensor(self):
        """Test the max sensor."""
        config = {
            "sensor": {
                "platform": "min_max",
                "name": "test_max",
                "type": "max",
                "entity_ids": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
            }
        }

        assert setup_component(self.hass, "sensor", config)

        entity_ids = config["sensor"]["entity_ids"]

        for entity_id, value in dict(zip(entity_ids, self.values)).items():
            self.hass.states.set(entity_id, value)
            self.hass.block_till_done()

        state = self.hass.states.get("sensor.test_max")

        assert str(float(self.max)) == state.state
        assert entity_ids[2] == state.attributes.get("min_entity_id")
        assert self.min == state.attributes.get("min_value")
        assert entity_ids[1] == state.attributes.get("max_entity_id")
        assert self.mean == state.attributes.get("mean")
        assert self.median == state.attributes.get("median")

    def test_mean_sensor(self):
        """Test the mean sensor."""
        config = {
            "sensor": {
                "platform": "min_max",
                "name": "test_mean",
                "type": "mean",
                "entity_ids": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
            }
        }

        assert setup_component(self.hass, "sensor", config)

        entity_ids = config["sensor"]["entity_ids"]

        for entity_id, value in dict(zip(entity_ids, self.values)).items():
            self.hass.states.set(entity_id, value)
            self.hass.block_till_done()

        state = self.hass.states.get("sensor.test_mean")

        assert str(float(self.mean)) == state.state
        assert self.min == state.attributes.get("min_value")
        assert entity_ids[2] == state.attributes.get("min_entity_id")
        assert self.max == state.attributes.get("max_value")
        assert entity_ids[1] == state.attributes.get("max_entity_id")
        assert self.median == state.attributes.get("median")

    def test_mean_1_digit_sensor(self):
        """Test the mean with 1-digit precision sensor."""
        config = {
            "sensor": {
                "platform": "min_max",
                "name": "test_mean",
                "type": "mean",
                "round_digits": 1,
                "entity_ids": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
            }
        }

        assert setup_component(self.hass, "sensor", config)

        entity_ids = config["sensor"]["entity_ids"]

        for entity_id, value in dict(zip(entity_ids, self.values)).items():
            self.hass.states.set(entity_id, value)
            self.hass.block_till_done()

        state = self.hass.states.get("sensor.test_mean")

        assert str(float(self.mean_1_digit)) == state.state
        assert self.min == state.attributes.get("min_value")
        assert entity_ids[2] == state.attributes.get("min_entity_id")
        assert self.max == state.attributes.get("max_value")
        assert entity_ids[1] == state.attributes.get("max_entity_id")
        assert self.median == state.attributes.get("median")

    def test_mean_4_digit_sensor(self):
        """Test the mean with 1-digit precision sensor."""
        config = {
            "sensor": {
                "platform": "min_max",
                "name": "test_mean",
                "type": "mean",
                "round_digits": 4,
                "entity_ids": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
            }
        }

        assert setup_component(self.hass, "sensor", config)

        entity_ids = config["sensor"]["entity_ids"]

        for entity_id, value in dict(zip(entity_ids, self.values)).items():
            self.hass.states.set(entity_id, value)
            self.hass.block_till_done()

        state = self.hass.states.get("sensor.test_mean")

        assert str(float(self.mean_4_digits)) == state.state
        assert self.min == state.attributes.get("min_value")
        assert entity_ids[2] == state.attributes.get("min_entity_id")
        assert self.max == state.attributes.get("max_value")
        assert entity_ids[1] == state.attributes.get("max_entity_id")
        assert self.median == state.attributes.get("median")

    def test_median_sensor(self):
        """Test the median sensor."""
        config = {
            "sensor": {
                "platform": "min_max",
                "name": "test_median",
                "type": "median",
                "entity_ids": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
            }
        }

        assert setup_component(self.hass, "sensor", config)

        entity_ids = config["sensor"]["entity_ids"]

        for entity_id, value in dict(zip(entity_ids, self.values)).items():
            self.hass.states.set(entity_id, value)
            self.hass.block_till_done()

        state = self.hass.states.get("sensor.test_median")

        assert str(float(self.median)) == state.state
        assert self.min == state.attributes.get("min_value")
        assert entity_ids[2] == state.attributes.get("min_entity_id")
        assert self.max == state.attributes.get("max_value")
        assert entity_ids[1] == state.attributes.get("max_entity_id")
        assert self.mean == state.attributes.get("mean")

    def test_not_enough_sensor_value(self):
        """Test that there is nothing done if not enough values available."""
        config = {
            "sensor": {
                "platform": "min_max",
                "name": "test_max",
                "type": "max",
                "entity_ids": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
            }
        }

        assert setup_component(self.hass, "sensor", config)

        entity_ids = config["sensor"]["entity_ids"]

        self.hass.states.set(entity_ids[0], STATE_UNKNOWN)
        self.hass.block_till_done()

        state = self.hass.states.get("sensor.test_max")
        assert STATE_UNKNOWN == state.state
        assert state.attributes.get("min_entity_id") is None
        assert state.attributes.get("min_value") is None
        assert state.attributes.get("max_entity_id") is None
        assert state.attributes.get("max_value") is None
        assert state.attributes.get("median") is None

        self.hass.states.set(entity_ids[1], self.values[1])
        self.hass.block_till_done()

        state = self.hass.states.get("sensor.test_max")
        assert STATE_UNKNOWN != state.state
        assert entity_ids[1] == state.attributes.get("min_entity_id")
        assert self.values[1] == state.attributes.get("min_value")
        assert entity_ids[1] == state.attributes.get("max_entity_id")
        assert self.values[1] == state.attributes.get("max_value")

        self.hass.states.set(entity_ids[2], STATE_UNKNOWN)
        self.hass.block_till_done()

        state = self.hass.states.get("sensor.test_max")
        assert STATE_UNKNOWN != state.state
        assert entity_ids[1] == state.attributes.get("min_entity_id")
        assert self.values[1] == state.attributes.get("min_value")
        assert entity_ids[1] == state.attributes.get("max_entity_id")
        assert self.values[1] == state.attributes.get("max_value")

        self.hass.states.set(entity_ids[1], STATE_UNAVAILABLE)
        self.hass.block_till_done()

        state = self.hass.states.get("sensor.test_max")
        assert STATE_UNKNOWN == state.state
        assert state.attributes.get("min_entity_id") is None
        assert state.attributes.get("min_value") is None
        assert state.attributes.get("max_entity_id") is None
        assert state.attributes.get("max_value") is None

    def test_different_unit_of_measurement(self):
        """Test for different unit of measurement."""
        config = {
            "sensor": {
                "platform": "min_max",
                "name": "test",
                "type": "mean",
                "entity_ids": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
            }
        }

        assert setup_component(self.hass, "sensor", config)

        entity_ids = config["sensor"]["entity_ids"]

        self.hass.states.set(
            entity_ids[0], self.values[0], {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS}
        )
        self.hass.block_till_done()

        state = self.hass.states.get("sensor.test")

        assert str(float(self.values[0])) == state.state
        assert state.attributes.get("unit_of_measurement") == TEMP_CELSIUS

        self.hass.states.set(
            entity_ids[1], self.values[1], {ATTR_UNIT_OF_MEASUREMENT: TEMP_FAHRENHEIT}
        )
        self.hass.block_till_done()

        state = self.hass.states.get("sensor.test")

        assert STATE_UNKNOWN == state.state
        assert state.attributes.get("unit_of_measurement") == "ERR"

        self.hass.states.set(
            entity_ids[2], self.values[2], {ATTR_UNIT_OF_MEASUREMENT: UNIT_PERCENTAGE}
        )
        self.hass.block_till_done()

        state = self.hass.states.get("sensor.test")

        assert STATE_UNKNOWN == state.state
        assert state.attributes.get("unit_of_measurement") == "ERR"

    def test_last_sensor(self):
        """Test the last sensor."""
        config = {
            "sensor": {
                "platform": "min_max",
                "name": "test_last",
                "type": "last",
                "entity_ids": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
            }
        }

        assert setup_component(self.hass, "sensor", config)

        entity_ids = config["sensor"]["entity_ids"]
        state = self.hass.states.get("sensor.test_last")

        for entity_id, value in dict(zip(entity_ids, self.values)).items():
            self.hass.states.set(entity_id, value)
            self.hass.block_till_done()
            state = self.hass.states.get("sensor.test_last")
            assert str(float(value)) == state.state
            assert entity_id == state.attributes.get("last_entity_id")

        assert self.min == state.attributes.get("min_value")
        assert self.max == state.attributes.get("max_value")
        assert self.mean == state.attributes.get("mean")
        assert self.median == state.attributes.get("median")
