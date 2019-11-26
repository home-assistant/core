"""The test for the bayesian sensor platform."""
import unittest
from datetime import timedelta

from homeassistant.setup import setup_component, async_setup_component
from homeassistant.components.bayesian import binary_sensor as bayesian
import homeassistant.util.dt as dt_util

from tests.common import get_test_home_assistant, async_fire_time_changed


class TestBayesianBinarySensor(unittest.TestCase):
    """Test the threshold sensor."""

    def setup_method(self, method):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_sensor_numeric_state(self):
        """Test sensor on numeric state platform observations."""
        config = {
            "binary_sensor": {
                "platform": "bayesian",
                "name": "Test_Binary",
                "observations": [
                    {
                        "platform": "numeric_state",
                        "entity_id": "sensor.test_monitored",
                        "below": 10,
                        "above": 5,
                        "prob_given_true": 0.6,
                    },
                    {
                        "platform": "numeric_state",
                        "entity_id": "sensor.test_monitored1",
                        "below": 7,
                        "above": 5,
                        "prob_given_true": 0.9,
                        "prob_given_false": 0.1,
                    },
                ],
                "prior": 0.2,
            }
        }

        assert setup_component(self.hass, "binary_sensor", config)

        self.hass.states.set("sensor.test_monitored", 4)
        self.hass.block_till_done()

        state = self.hass.states.get("binary_sensor.test_binary")

        assert len(state.attributes.get("observations")) == 0
        assert state.attributes.get("probability") == 0.2

        assert state.state == "off"

        self.hass.states.set("sensor.test_monitored", 6)
        self.hass.block_till_done()
        self.hass.states.set("sensor.test_monitored", 4)
        self.hass.block_till_done()
        self.hass.states.set("sensor.test_monitored", 6)
        self.hass.states.set("sensor.test_monitored1", 6)
        self.hass.block_till_done()

        state = self.hass.states.get("binary_sensor.test_binary")
        assert [
            {"prob_false": 0.4, "prob_true": 0.6},
            {"prob_false": 0.1, "prob_true": 0.9},
        ] == state.attributes.get("observations")
        assert round(abs(0.77 - state.attributes.get("probability")), 7) == 0

        assert state.state == "on"

        self.hass.states.set("sensor.test_monitored", 6)
        self.hass.states.set("sensor.test_monitored1", 0)
        self.hass.block_till_done()
        self.hass.states.set("sensor.test_monitored", 4)
        self.hass.block_till_done()

        state = self.hass.states.get("binary_sensor.test_binary")
        assert state.attributes.get("probability") == 0.2

        assert state.state == "off"

        self.hass.states.set("sensor.test_monitored", 15)
        self.hass.block_till_done()

        state = self.hass.states.get("binary_sensor.test_binary")

        assert state.state == "off"

    def test_sensor_state(self):
        """Test sensor on state platform observations."""
        config = {
            "binary_sensor": {
                "name": "Test_Binary",
                "platform": "bayesian",
                "observations": [
                    {
                        "platform": "state",
                        "entity_id": "sensor.test_monitored",
                        "to_state": "off",
                        "prob_given_true": 0.8,
                        "prob_given_false": 0.4,
                    }
                ],
                "prior": 0.2,
                "probability_threshold": 0.32,
            }
        }

        assert setup_component(self.hass, "binary_sensor", config)

        self.hass.states.set("sensor.test_monitored", "on")

        state = self.hass.states.get("binary_sensor.test_binary")

        assert len(state.attributes.get("observations")) == 0
        assert state.attributes.get("probability") == 0.2

        assert state.state == "off"

        self.hass.states.set("sensor.test_monitored", "off")
        self.hass.block_till_done()
        self.hass.states.set("sensor.test_monitored", "on")
        self.hass.block_till_done()
        self.hass.states.set("sensor.test_monitored", "off")
        self.hass.block_till_done()

        state = self.hass.states.get("binary_sensor.test_binary")
        assert [{"prob_true": 0.8, "prob_false": 0.4}] == state.attributes.get(
            "observations"
        )
        assert round(abs(0.33 - state.attributes.get("probability")), 7) == 0

        assert state.state == "on"

        self.hass.states.set("sensor.test_monitored", "off")
        self.hass.block_till_done()
        self.hass.states.set("sensor.test_monitored", "on")
        self.hass.block_till_done()

        state = self.hass.states.get("binary_sensor.test_binary")
        assert round(abs(0.2 - state.attributes.get("probability")), 7) == 0

        assert state.state == "off"

    def test_sensor_template(self):
        """Test sensor on template platform observations."""
        config = {
            "binary_sensor": {
                "name": "Test_Binary",
                "platform": "bayesian",
                "observations": [
                    {
                        "platform": "template",
                        "value_template": "{{ is_state('sensor.test_monitored1', 'on') "
                        "and is_state('sensor.test_monitored2', 'on') }}",
                        "prob_given_true": 0.8,
                        "prob_given_false": 0.2,
                    },
                    {
                        "platform": "template",
                        "value_template": "{{ is_state('sensor.test_monitored1', 'off') "
                        "and is_state('sensor.test_monitored2', 'on') }}",
                        "prob_given_true": 0.4,
                        "prob_given_false": 0.9,
                    },
                ],
                "prior": 0.2,
                "probability_threshold": 0.3,
            }
        }

        assert setup_component(self.hass, "binary_sensor", config)

        self.hass.states.set("sensor.test_monitored1", "on")
        self.hass.states.set("sensor.test_monitored2", "off")
        self.hass.block_till_done()

        state = self.hass.states.get("binary_sensor.test_binary")

        assert len(state.attributes.get("observations")) == 0
        assert state.attributes.get("probability") == 0.2

        assert state.state == "off"

        self.hass.states.set("sensor.test_monitored2", "on")
        self.hass.block_till_done()

        state = self.hass.states.get("binary_sensor.test_binary")
        assert len(state.attributes.get("observations")) == 1
        assert abs(0.5 - state.attributes.get("probability")) < 1e-7
        assert state.state == "on"

        self.hass.states.set("sensor.test_monitored1", "off")
        self.hass.block_till_done()

        state = self.hass.states.get("binary_sensor.test_binary")
        assert len(state.attributes.get("observations")) == 1
        assert abs(0.1 - state.attributes.get("probability")) < 1e-7
        assert state.state == "off"

        self.hass.states.set("sensor.test_monitored2", "off")
        self.hass.block_till_done()

        state = self.hass.states.get("binary_sensor.test_binary")
        assert len(state.attributes.get("observations")) == 0
        assert abs(0.2 - state.attributes.get("probability")) < 1e-7
        assert state.state == "off"

    def test_threshold(self):
        """Test sensor on probabilty threshold limits."""
        config = {
            "binary_sensor": {
                "name": "Test_Binary",
                "platform": "bayesian",
                "observations": [
                    {
                        "platform": "state",
                        "entity_id": "sensor.test_monitored",
                        "to_state": "on",
                        "prob_given_true": 1.0,
                    }
                ],
                "prior": 0.5,
                "probability_threshold": 1.0,
            }
        }

        assert setup_component(self.hass, "binary_sensor", config)

        self.hass.states.set("sensor.test_monitored", "on")
        self.hass.block_till_done()

        state = self.hass.states.get("binary_sensor.test_binary")
        assert round(abs(1.0 - state.attributes.get("probability")), 7) == 0

        assert state.state == "on"

    def test_multiple_observations(self):
        """Test sensor with multiple observations of same entity."""
        config = {
            "binary_sensor": {
                "name": "Test_Binary",
                "platform": "bayesian",
                "observations": [
                    {
                        "platform": "state",
                        "entity_id": "sensor.test_monitored",
                        "to_state": "blue",
                        "prob_given_true": 0.8,
                        "prob_given_false": 0.4,
                    },
                    {
                        "platform": "state",
                        "entity_id": "sensor.test_monitored",
                        "to_state": "red",
                        "prob_given_true": 0.2,
                        "prob_given_false": 0.4,
                    },
                ],
                "prior": 0.2,
                "probability_threshold": 0.32,
            }
        }

        assert setup_component(self.hass, "binary_sensor", config)

        self.hass.states.set("sensor.test_monitored", "off")

        state = self.hass.states.get("binary_sensor.test_binary")

        assert len(state.attributes.get("observations")) == 0
        assert state.attributes.get("probability") == 0.2

        assert state.state == "off"

        self.hass.states.set("sensor.test_monitored", "blue")
        self.hass.block_till_done()
        self.hass.states.set("sensor.test_monitored", "off")
        self.hass.block_till_done()
        self.hass.states.set("sensor.test_monitored", "blue")
        self.hass.block_till_done()

        state = self.hass.states.get("binary_sensor.test_binary")
        assert [{"prob_true": 0.8, "prob_false": 0.4}] == state.attributes.get(
            "observations"
        )
        assert round(abs(0.33 - state.attributes.get("probability")), 7) == 0

        assert state.state == "on"

        self.hass.states.set("sensor.test_monitored", "blue")
        self.hass.block_till_done()
        self.hass.states.set("sensor.test_monitored", "red")
        self.hass.block_till_done()

        state = self.hass.states.get("binary_sensor.test_binary")
        assert round(abs(0.11 - state.attributes.get("probability")), 7) == 0

        assert state.state == "off"

    def test_probability_updates(self):
        """Test probability update function."""
        prob_true = [0.3, 0.6, 0.8]
        prob_false = [0.7, 0.4, 0.2]
        prior = 0.5

        for pt, pf in zip(prob_true, prob_false):
            prior = bayesian.update_probability(prior, pt, pf)

        assert round(abs(0.720000 - prior), 7) == 0

        prob_true = [0.8, 0.3, 0.9]
        prob_false = [0.6, 0.4, 0.2]
        prior = 0.7

        for pt, pf in zip(prob_true, prob_false):
            prior = bayesian.update_probability(prior, pt, pf)

        assert round(abs(0.9130434782608695 - prior), 7) == 0


async def test_state_delay_on(hass):
    """Test binary sensor state delay on."""
    config = {
        "binary_sensor": {
            "name": "test",
            "platform": "bayesian",
            "observations": [
                {
                    "platform": "state",
                    "entity_id": "sensor.test_state",
                    "to_state": "on",
                    "prob_given_true": 0.8,
                    "prob_given_false": 0.2,
                    "delay_on": 5,
                }
            ],
            "prior": 0.2,
            "probability_threshold": 0.3,
        }
    }
    await async_setup_component(hass, "binary_sensor", config)
    await hass.async_start()

    hass.states.async_set("sensor.test_state", "off")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"

    hass.states.async_set("sensor.test_state", "on")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"

    newtime = dt_util.utcnow() + timedelta(seconds=5)
    async_fire_time_changed(hass, newtime)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "on"

    # check with time changes
    hass.states.async_set("sensor.test_state", "off")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"

    hass.states.async_set("sensor.test_state", "on")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"

    hass.states.async_set("sensor.test_state", "off")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"

    newtime = dt_util.utcnow() + timedelta(seconds=5)
    async_fire_time_changed(hass, newtime)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"


async def test_state_delay_off(hass):
    """Test binary sensor state delay off."""
    config = {
        "binary_sensor": {
            "name": "test",
            "platform": "bayesian",
            "observations": [
                {
                    "platform": "state",
                    "entity_id": "sensor.test_state",
                    "to_state": "on",
                    "prob_given_true": 0.8,
                    "prob_given_false": 0.2,
                    "delay_off": 5,
                }
            ],
            "prior": 0.2,
            "probability_threshold": 0.3,
        }
    }
    await async_setup_component(hass, "binary_sensor", config)
    await hass.async_start()

    hass.states.async_set("sensor.test_state", "on")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "on"

    hass.states.async_set("sensor.test_state", "off")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "on"

    newtime = dt_util.utcnow() + timedelta(seconds=5)
    async_fire_time_changed(hass, newtime)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"

    # check with time changes
    hass.states.async_set("sensor.test_state", "on")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "on"

    hass.states.async_set("sensor.test_state", "off")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "on"

    hass.states.async_set("sensor.test_state", "on")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "on"

    newtime = newtime + timedelta(seconds=5)
    async_fire_time_changed(hass, newtime)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "on"


async def test_numeric_delay_on(hass):
    """Test binary sensor numeric delay on."""
    config = {
        "binary_sensor": {
            "name": "test",
            "platform": "bayesian",
            "observations": [
                {
                    "platform": "numeric_state",
                    "entity_id": "sensor.test_state",
                    "above": 10,
                    "prob_given_true": 0.8,
                    "prob_given_false": 0.2,
                    "delay_on": 5,
                }
            ],
            "prior": 0.2,
            "probability_threshold": 0.3,
        }
    }
    await async_setup_component(hass, "binary_sensor", config)
    await hass.async_start()

    hass.states.async_set("sensor.test_state", 5)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"

    hass.states.async_set("sensor.test_state", 15)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"

    newtime = dt_util.utcnow() + timedelta(seconds=5)
    async_fire_time_changed(hass, newtime)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "on"

    # check with time changes
    hass.states.async_set("sensor.test_state", 5)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"

    hass.states.async_set("sensor.test_state", 15)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"

    hass.states.async_set("sensor.test_state", 5)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"

    newtime = dt_util.utcnow() + timedelta(seconds=5)
    async_fire_time_changed(hass, newtime)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"


async def test_numeric_delay_off(hass):
    """Test binary sensor numeric delay off."""
    config = {
        "binary_sensor": {
            "name": "test",
            "platform": "bayesian",
            "observations": [
                {
                    "platform": "numeric_state",
                    "entity_id": "sensor.test_state",
                    "above": 10,
                    "prob_given_true": 0.8,
                    "prob_given_false": 0.2,
                    "delay_off": 5,
                }
            ],
            "prior": 0.2,
            "probability_threshold": 0.3,
        }
    }
    await async_setup_component(hass, "binary_sensor", config)
    await hass.async_start()

    hass.states.async_set("sensor.test_state", 15)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "on"

    hass.states.async_set("sensor.test_state", 5)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "on"

    newtime = dt_util.utcnow() + timedelta(seconds=5)
    async_fire_time_changed(hass, newtime)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"

    # check with time changes
    hass.states.async_set("sensor.test_state", 15)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "on"

    hass.states.async_set("sensor.test_state", 5)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "on"

    hass.states.async_set("sensor.test_state", 15)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "on"

    newtime = dt_util.utcnow() + timedelta(seconds=5)
    async_fire_time_changed(hass, newtime)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "on"


async def test_template_delay_on(hass):
    """Test binary sensor template delay on."""
    config = {
        "binary_sensor": {
            "name": "test",
            "platform": "bayesian",
            "observations": [
                {
                    "platform": "template",
                    "value_template": "{{ is_state('sensor.test_state1', 'on') "
                    "and is_state('sensor.test_state2', 'on') }}",
                    "prob_given_true": 0.8,
                    "prob_given_false": 0.2,
                    "delay_on": 5,
                },
            ],
            "prior": 0.2,
            "probability_threshold": 0.3,
        }
    }
    await async_setup_component(hass, "binary_sensor", config)
    await hass.async_start()

    hass.states.async_set("sensor.test_state1", "off")
    hass.states.async_set("sensor.test_state2", "off")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"

    hass.states.async_set("sensor.test_state1", "on")
    hass.states.async_set("sensor.test_state2", "on")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"

    newtime = dt_util.utcnow() + timedelta(seconds=5)
    async_fire_time_changed(hass, newtime)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "on"

    # check with time changes
    hass.states.async_set("sensor.test_state1", "on")
    hass.states.async_set("sensor.test_state2", "off")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"

    hass.states.async_set("sensor.test_state2", "on")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"

    hass.states.async_set("sensor.test_state2", "off")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"

    newtime = dt_util.utcnow() + timedelta(seconds=5)
    async_fire_time_changed(hass, newtime)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"


async def test_template_delay_off(hass):
    """Test binary sensor template delay off."""
    config = {
        "binary_sensor": {
            "name": "test",
            "platform": "bayesian",
            "observations": [
                {
                    "platform": "template",
                    "value_template": "{{ is_state('sensor.test_state1', 'on') "
                    "and is_state('sensor.test_state2', 'on') }}",
                    "prob_given_true": 0.8,
                    "prob_given_false": 0.2,
                    "delay_off": 5,
                },
            ],
            "prior": 0.2,
            "probability_threshold": 0.3,
        }
    }
    await async_setup_component(hass, "binary_sensor", config)
    await hass.async_start()

    hass.states.async_set("sensor.test_state1", "on")
    hass.states.async_set("sensor.test_state2", "on")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "on"

    hass.states.async_set("sensor.test_state1", "off")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "on"

    newtime = dt_util.utcnow() + timedelta(seconds=5)
    async_fire_time_changed(hass, newtime)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"

    # check with time changes
    hass.states.async_set("sensor.test_state1", "on")
    hass.states.async_set("sensor.test_state2", "on")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "on"

    hass.states.async_set("sensor.test_state2", "off")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "on"

    hass.states.async_set("sensor.test_state2", "on")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "on"

    newtime = dt_util.utcnow() + timedelta(seconds=5)
    async_fire_time_changed(hass, newtime)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "on"


async def test_state_delay_on_off(hass):
    """Test binary sensor numeric using both delay on and off."""
    config = {
        "binary_sensor": {
            "name": "test",
            "platform": "bayesian",
            "observations": [
                {
                    "platform": "numeric_state",
                    "entity_id": "sensor.test_state",
                    "above": 10,
                    "prob_given_true": 0.8,
                    "prob_given_false": 0.2,
                    "delay_on": 5,
                    "delay_off": 5,
                }
            ],
            "prior": 0.2,
            "probability_threshold": 0.3,
        }
    }
    await async_setup_component(hass, "binary_sensor", config)
    await hass.async_start()

    hass.states.async_set("sensor.test_state", 5)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"

    hass.states.async_set("sensor.test_state", 15)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"

    newtime = dt_util.utcnow() + timedelta(seconds=5)
    async_fire_time_changed(hass, newtime)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "on"

    hass.states.async_set("sensor.test_state", 5)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "on"

    newtime = dt_util.utcnow() + timedelta(seconds=5)
    async_fire_time_changed(hass, newtime)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"

    # check with time changes
    hass.states.async_set("sensor.test_state", 15)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"

    hass.states.async_set("sensor.test_state", 5)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"

    newtime = dt_util.utcnow() + timedelta(seconds=5)
    async_fire_time_changed(hass, newtime)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"

    hass.states.async_set("sensor.test_state", 15)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"

    hass.states.async_set("sensor.test_state", 5)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"

    hass.states.async_set("sensor.test_state", 15)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"

    newtime = dt_util.utcnow() + timedelta(seconds=5)
    async_fire_time_changed(hass, newtime)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "on"


async def test_state_max_duration(hass):
    """Test binary sensor state using max duration."""
    config = {
        "binary_sensor": {
            "name": "test",
            "platform": "bayesian",
            "observations": [
                {
                    "platform": "state",
                    "entity_id": "sensor.test_state",
                    "prob_given_true": 0.6,
                    "prob_given_false": 0.35,
                    "to_state": "on",
                    "max_duration": 5,
                },
                {
                    "platform": "state",
                    "entity_id": "sensor.test_state",
                    "to_state": "on",
                    "prob_given_true": 0.8,
                    "prob_given_false": 0.2,
                    "delay_on": 5,
                    "max_duration": 5,
                },
                {
                    "platform": "state",
                    "entity_id": "sensor.test_state",
                    "to_state": "off",
                    "prob_given_true": 0.52,
                    "prob_given_false": 0.39,
                    "max_duration": 3,
                },
                {
                    "platform": "state",
                    "entity_id": "sensor.test_state",
                    "to_state": "off",
                    "prob_given_true": 0.28,
                    "prob_given_false": 0.63,
                    "delay_on": 3,
                    "max_duration": 5,
                },
            ],
            "prior": 0.2,
            "probability_threshold": 0.3,
        }
    }

    await async_setup_component(hass, "binary_sensor", config)
    await hass.async_start()

    hass.states.async_set("sensor.test_state", "on")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "on"
    assert [{"prob_false": 0.35, "prob_true": 0.6}] == state.attributes.get(
        "observations"
    )
    assert abs(0.3 - state.attributes.get("probability")) < 1e-7

    newtime = dt_util.utcnow() + timedelta(seconds=5)
    async_fire_time_changed(hass, newtime)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "on"
    assert [{"prob_false": 0.2, "prob_true": 0.8}] == state.attributes.get(
        "observations"
    )
    assert abs(0.5 - state.attributes.get("probability")) < 1e-7

    newtime = newtime + timedelta(seconds=5)
    async_fire_time_changed(hass, newtime)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"
    assert [] == state.attributes.get("observations")
    assert abs(0.2 - state.attributes.get("probability")) < 1e-7

    newtime = newtime + timedelta(seconds=1)
    async_fire_time_changed(hass, newtime)
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_state", "off")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"
    assert [{"prob_false": 0.39, "prob_true": 0.52}] == state.attributes.get(
        "observations"
    )
    assert abs(0.25 - state.attributes.get("probability")) < 1e-7

    newtime = newtime + timedelta(seconds=3)
    async_fire_time_changed(hass, newtime)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"
    assert [{"prob_false": 0.63, "prob_true": 0.28}] == state.attributes.get(
        "observations"
    )
    assert abs(0.1 - state.attributes.get("probability")) < 1e-7

    newtime = newtime + timedelta(seconds=5)
    async_fire_time_changed(hass, newtime)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test")
    assert state.state == "off"
    assert [] == state.attributes.get("observations")
    assert abs(0.2 - state.attributes.get("probability")) < 1e-7
