"""The test for the bayesian sensor platform."""
import json
from os import path
from unittest.mock import patch

from homeassistant import config as hass_config
from homeassistant.components.bayesian import DOMAIN, binary_sensor as bayesian
from homeassistant.components.homeassistant import (
    DOMAIN as HA_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_RELOAD,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import Context, callback
from homeassistant.setup import async_setup_component


async def test_load_values_when_added_to_hass(hass):
    """Test that sensor initializes with observations of relevant entities."""

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

    hass.states.async_set("sensor.test_monitored", "off")
    await hass.async_block_till_done()

    assert await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_binary")
    assert state.attributes.get("observations")[0]["prob_given_true"] == 0.8
    assert state.attributes.get("observations")[0]["prob_given_false"] == 0.4


async def test_unknown_state_does_not_influence_probability(hass):
    """Test that an unknown state does not change the output probability."""

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

    hass.states.async_set("sensor.test_monitored", STATE_UNKNOWN)
    await hass.async_block_till_done()

    assert await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_binary")
    assert state.attributes.get("observations") == []


async def test_sensor_numeric_state(hass):
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

    assert await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()

    hass.states.async_set("sensor.test_monitored", 4)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_binary")

    assert [] == state.attributes.get("observations")
    assert 0.2 == state.attributes.get("probability")

    assert state.state == "off"

    hass.states.async_set("sensor.test_monitored", 6)
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_monitored", 4)
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_monitored", 6)
    hass.states.async_set("sensor.test_monitored1", 6)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_binary")
    assert state.attributes.get("observations")[0]["prob_given_true"] == 0.6
    assert state.attributes.get("observations")[1]["prob_given_true"] == 0.9
    assert state.attributes.get("observations")[1]["prob_given_false"] == 0.1
    assert round(abs(0.77 - state.attributes.get("probability")), 7) == 0

    assert state.state == "on"

    hass.states.async_set("sensor.test_monitored", 6)
    hass.states.async_set("sensor.test_monitored1", 0)
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_monitored", 4)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_binary")
    assert 0.2 == state.attributes.get("probability")

    assert state.state == "off"

    hass.states.async_set("sensor.test_monitored", 15)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_binary")

    assert state.state == "off"


async def test_sensor_state(hass):
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

    assert await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()

    hass.states.async_set("sensor.test_monitored", "on")

    state = hass.states.get("binary_sensor.test_binary")

    assert [] == state.attributes.get("observations")
    assert 0.2 == state.attributes.get("probability")

    assert state.state == "off"

    hass.states.async_set("sensor.test_monitored", "off")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_monitored", "on")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_monitored", "off")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_binary")
    assert state.attributes.get("observations")[0]["prob_given_true"] == 0.8
    assert state.attributes.get("observations")[0]["prob_given_false"] == 0.4
    assert round(abs(0.33 - state.attributes.get("probability")), 7) == 0

    assert state.state == "on"

    hass.states.async_set("sensor.test_monitored", "off")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_monitored", "on")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_binary")
    assert round(abs(0.2 - state.attributes.get("probability")), 7) == 0

    assert state.state == "off"


async def test_sensor_value_template(hass):
    """Test sensor on template platform observations."""
    config = {
        "binary_sensor": {
            "name": "Test_Binary",
            "platform": "bayesian",
            "observations": [
                {
                    "platform": "template",
                    "value_template": "{{states('sensor.test_monitored') == 'off'}}",
                    "prob_given_true": 0.8,
                    "prob_given_false": 0.4,
                }
            ],
            "prior": 0.2,
            "probability_threshold": 0.32,
        }
    }

    assert await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()

    hass.states.async_set("sensor.test_monitored", "on")

    state = hass.states.get("binary_sensor.test_binary")

    assert [] == state.attributes.get("observations")
    assert 0.2 == state.attributes.get("probability")

    assert state.state == "off"

    hass.states.async_set("sensor.test_monitored", "off")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_monitored", "on")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_monitored", "off")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_binary")
    assert state.attributes.get("observations")[0]["prob_given_true"] == 0.8
    assert state.attributes.get("observations")[0]["prob_given_false"] == 0.4
    assert round(abs(0.33 - state.attributes.get("probability")), 7) == 0

    assert state.state == "on"

    hass.states.async_set("sensor.test_monitored", "off")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_monitored", "on")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_binary")
    assert round(abs(0.2 - state.attributes.get("probability")), 7) == 0

    assert state.state == "off"


async def test_threshold(hass):
    """Test sensor on probability threshold limits."""
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

    assert await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()

    hass.states.async_set("sensor.test_monitored", "on")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_binary")
    assert round(abs(1.0 - state.attributes.get("probability")), 7) == 0

    assert state.state == "on"


async def test_multiple_observations(hass):
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

    assert await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()

    hass.states.async_set("sensor.test_monitored", "off")

    state = hass.states.get("binary_sensor.test_binary")

    for key, attrs in state.attributes.items():
        json.dumps(attrs)
    assert [] == state.attributes.get("observations")
    assert 0.2 == state.attributes.get("probability")

    assert state.state == "off"

    hass.states.async_set("sensor.test_monitored", "blue")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_monitored", "off")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_monitored", "blue")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_binary")

    assert state.attributes.get("observations")[0]["prob_given_true"] == 0.8
    assert state.attributes.get("observations")[0]["prob_given_false"] == 0.4
    assert round(abs(0.33 - state.attributes.get("probability")), 7) == 0

    assert state.state == "on"

    hass.states.async_set("sensor.test_monitored", "blue")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_monitored", "red")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_binary")
    assert round(abs(0.11 - state.attributes.get("probability")), 7) == 0

    assert state.state == "off"


async def test_probability_updates(hass):
    """Test probability update function."""
    prob_given_true = [0.3, 0.6, 0.8]
    prob_given_false = [0.7, 0.4, 0.2]
    prior = 0.5

    for pt, pf in zip(prob_given_true, prob_given_false):
        prior = bayesian.update_probability(prior, pt, pf)

    assert round(abs(0.720000 - prior), 7) == 0

    prob_given_true = [0.8, 0.3, 0.9]
    prob_given_false = [0.6, 0.4, 0.2]
    prior = 0.7

    for pt, pf in zip(prob_given_true, prob_given_false):
        prior = bayesian.update_probability(prior, pt, pf)

    assert round(abs(0.9130434782608695 - prior), 7) == 0


async def test_observed_entities(hass):
    """Test sensor on observed entities."""
    config = {
        "binary_sensor": {
            "name": "Test_Binary",
            "platform": "bayesian",
            "observations": [
                {
                    "platform": "state",
                    "entity_id": "sensor.test_monitored",
                    "to_state": "off",
                    "prob_given_true": 0.9,
                    "prob_given_false": 0.4,
                },
                {
                    "platform": "template",
                    "value_template": "{{is_state('sensor.test_monitored1','on') and is_state('sensor.test_monitored','off')}}",
                    "prob_given_true": 0.9,
                },
            ],
            "prior": 0.2,
            "probability_threshold": 0.32,
        }
    }

    assert await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()

    hass.states.async_set("sensor.test_monitored", "on")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_monitored1", "off")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_binary")
    assert [] == state.attributes.get("occurred_observation_entities")

    hass.states.async_set("sensor.test_monitored", "off")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_binary")
    assert ["sensor.test_monitored"] == state.attributes.get(
        "occurred_observation_entities"
    )

    hass.states.async_set("sensor.test_monitored1", "on")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_binary")
    assert ["sensor.test_monitored", "sensor.test_monitored1"] == sorted(
        state.attributes.get("occurred_observation_entities")
    )


async def test_state_attributes_are_serializable(hass):
    """Test sensor on observed entities."""
    config = {
        "binary_sensor": {
            "name": "Test_Binary",
            "platform": "bayesian",
            "observations": [
                {
                    "platform": "state",
                    "entity_id": "sensor.test_monitored",
                    "to_state": "off",
                    "prob_given_true": 0.9,
                    "prob_given_false": 0.4,
                },
                {
                    "platform": "template",
                    "value_template": "{{is_state('sensor.test_monitored1','on') and is_state('sensor.test_monitored','off')}}",
                    "prob_given_true": 0.9,
                },
            ],
            "prior": 0.2,
            "probability_threshold": 0.32,
        }
    }

    assert await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()

    hass.states.async_set("sensor.test_monitored", "on")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_monitored1", "off")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_binary")
    assert [] == state.attributes.get("occurred_observation_entities")

    hass.states.async_set("sensor.test_monitored", "off")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_binary")
    assert ["sensor.test_monitored"] == state.attributes.get(
        "occurred_observation_entities"
    )

    hass.states.async_set("sensor.test_monitored1", "on")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_binary")
    assert ["sensor.test_monitored", "sensor.test_monitored1"] == sorted(
        state.attributes.get("occurred_observation_entities")
    )

    for key, attrs in state.attributes.items():
        json.dumps(attrs)


async def test_template_error(hass, caplog):
    """Test sensor with template error."""
    config = {
        "binary_sensor": {
            "name": "Test_Binary",
            "platform": "bayesian",
            "observations": [
                {
                    "platform": "template",
                    "value_template": "{{ xyz + 1 }}",
                    "prob_given_true": 0.9,
                },
            ],
            "prior": 0.2,
            "probability_threshold": 0.32,
        }
    }

    await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.test_binary").state == "off"

    assert "TemplateError" in caplog.text
    assert "xyz" in caplog.text


async def test_update_request_with_template(hass):
    """Test sensor on template platform observations that gets an update request."""
    config = {
        "binary_sensor": {
            "name": "Test_Binary",
            "platform": "bayesian",
            "observations": [
                {
                    "platform": "template",
                    "value_template": "{{states('sensor.test_monitored') == 'off'}}",
                    "prob_given_true": 0.8,
                    "prob_given_false": 0.4,
                }
            ],
            "prior": 0.2,
            "probability_threshold": 0.32,
        }
    }

    await async_setup_component(hass, "binary_sensor", config)
    await async_setup_component(hass, HA_DOMAIN, {})

    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.test_binary").state == "off"

    await hass.services.async_call(
        HA_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: "binary_sensor.test_binary"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.test_binary").state == "off"


async def test_update_request_without_template(hass):
    """Test sensor on template platform observations that gets an update request."""
    config = {
        "binary_sensor": {
            "name": "Test_Binary",
            "platform": "bayesian",
            "observations": [
                {
                    "platform": "state",
                    "entity_id": "sensor.test_monitored",
                    "to_state": "off",
                    "prob_given_true": 0.9,
                    "prob_given_false": 0.4,
                },
            ],
            "prior": 0.2,
            "probability_threshold": 0.32,
        }
    }

    await async_setup_component(hass, "binary_sensor", config)
    await async_setup_component(hass, HA_DOMAIN, {})

    await hass.async_block_till_done()

    hass.states.async_set("sensor.test_monitored", "on")
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.test_binary").state == "off"

    await hass.services.async_call(
        HA_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: "binary_sensor.test_binary"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.test_binary").state == "off"


async def test_monitored_sensor_goes_away(hass):
    """Test sensor on template platform observations that goes away."""
    config = {
        "binary_sensor": {
            "name": "Test_Binary",
            "platform": "bayesian",
            "observations": [
                {
                    "platform": "state",
                    "entity_id": "sensor.test_monitored",
                    "to_state": "on",
                    "prob_given_true": 0.9,
                    "prob_given_false": 0.4,
                },
            ],
            "prior": 0.2,
            "probability_threshold": 0.32,
        }
    }

    await async_setup_component(hass, "binary_sensor", config)
    await async_setup_component(hass, HA_DOMAIN, {})

    await hass.async_block_till_done()

    hass.states.async_set("sensor.test_monitored", "on")
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.test_binary").state == "on"

    hass.states.async_remove("sensor.test_monitored")

    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.test_binary").state == "on"


async def test_reload(hass):
    """Verify we can reload bayesian sensors."""

    config = {
        "binary_sensor": {
            "name": "test",
            "platform": "bayesian",
            "observations": [
                {
                    "platform": "state",
                    "entity_id": "sensor.test_monitored",
                    "to_state": "on",
                    "prob_given_true": 0.9,
                    "prob_given_false": 0.4,
                },
            ],
            "prior": 0.2,
            "probability_threshold": 0.32,
        }
    }

    await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1

    assert hass.states.get("binary_sensor.test")

    yaml_path = path.join(
        _get_fixtures_base_path(),
        "fixtures",
        "bayesian/configuration.yaml",
    )
    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1

    assert hass.states.get("binary_sensor.test") is None
    assert hass.states.get("binary_sensor.test2")


def _get_fixtures_base_path():
    return path.dirname(path.dirname(path.dirname(__file__)))


async def test_template_triggers(hass):
    """Test sensor with template triggers."""
    hass.states.async_set("input_boolean.test", STATE_OFF)
    config = {
        "binary_sensor": {
            "name": "Test_Binary",
            "platform": "bayesian",
            "observations": [
                {
                    "platform": "template",
                    "value_template": "{{ states.input_boolean.test.state }}",
                    "prob_given_true": 1999.9,
                },
            ],
            "prior": 0.2,
            "probability_threshold": 0.32,
        }
    }

    await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.test_binary").state == STATE_OFF

    events = []
    hass.helpers.event.async_track_state_change_event(
        "binary_sensor.test_binary", callback(lambda event: events.append(event))
    )

    context = Context()
    hass.states.async_set("input_boolean.test", STATE_ON, context=context)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    assert events[0].context == context


async def test_state_triggers(hass):
    """Test sensor with state triggers."""
    hass.states.async_set("sensor.test_monitored", STATE_OFF)

    config = {
        "binary_sensor": {
            "name": "Test_Binary",
            "platform": "bayesian",
            "observations": [
                {
                    "platform": "state",
                    "entity_id": "sensor.test_monitored",
                    "to_state": "off",
                    "prob_given_true": 999.9,
                    "prob_given_false": 999.4,
                },
            ],
            "prior": 0.2,
            "probability_threshold": 0.32,
        }
    }
    await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.test_binary").state == STATE_OFF

    events = []
    hass.helpers.event.async_track_state_change_event(
        "binary_sensor.test_binary", callback(lambda event: events.append(event))
    )

    context = Context()
    hass.states.async_set("sensor.test_monitored", STATE_ON, context=context)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    assert events[0].context == context
