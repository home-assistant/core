"""The test for the bayesian sensor platform."""

import json
from unittest.mock import patch

import pytest

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
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.entity_registry import async_get as async_get_entities
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.setup import async_setup_component

from tests.common import get_fixture_path


async def test_load_values_when_added_to_hass(hass: HomeAssistant) -> None:
    """Test that sensor initializes with observations of relevant entities."""

    config = {
        "binary_sensor": {
            "name": "Test_Binary",
            "platform": "bayesian",
            "unique_id": "3b4c9563-5e84-4167-8fe7-8f507e796d72",
            "device_class": "connectivity",
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

    entity_registry = async_get_entities(hass)
    assert (
        entity_registry.entities["binary_sensor.test_binary"].unique_id
        == "bayesian-3b4c9563-5e84-4167-8fe7-8f507e796d72"
    )

    state = hass.states.get("binary_sensor.test_binary")
    assert state.attributes.get("device_class") == "connectivity"
    assert state.attributes.get("observations")[0]["prob_given_true"] == 0.8
    assert state.attributes.get("observations")[0]["prob_given_false"] == 0.4


async def test_unknown_state_does_not_influence_probability(
    hass: HomeAssistant,
) -> None:
    """Test that an unknown state does not change the output probability."""
    prior = 0.2
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
            "prior": prior,
            "probability_threshold": 0.32,
        }
    }
    hass.states.async_set("sensor.test_monitored", "on")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_monitored", STATE_UNKNOWN)
    await hass.async_block_till_done()

    assert await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_binary")
    assert state.attributes.get("occurred_observation_entities") == []
    assert state.attributes.get("probability") == prior


async def test_sensor_numeric_state(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
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
                    "prob_given_true": 0.7,
                    "prob_given_false": 0.4,
                },
                {
                    "platform": "numeric_state",
                    "entity_id": "sensor.test_monitored1",
                    "below": 7,
                    "above": 5,
                    "prob_given_true": 0.9,
                    "prob_given_false": 0.2,
                },
            ],
            "prior": 0.2,
        }
    }

    assert await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()

    hass.states.async_set("sensor.test_monitored", 6)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_binary")

    assert state.attributes.get("occurred_observation_entities") == [
        "sensor.test_monitored"
    ]
    assert abs(state.attributes.get("probability") - 0.304) < 0.01
    # A = sensor.test_binary being ON
    # B = sensor.test_monitored in the range [5, 10]
    # Bayes theorum  is P(A|B) = P(B|A) * P(A) / P(B|A)*P(A) + P(B|~A)*P(~A).
    # Where P(B|A) is prob_given_true and P(B|~A) is prob_given_false
    # Calculated using P(A) = 0.2, P(B|A) = 0.7, P(B|~A) = 0.4 -> 0.30

    hass.states.async_set("sensor.test_monitored", 4)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_binary")

    assert state.attributes.get("occurred_observation_entities") == [
        "sensor.test_monitored"
    ]
    assert abs(state.attributes.get("probability") - 0.111) < 0.01
    # As abve but since the value is equal to 4 then this is a negative observation (~B) where P(~B) == 1 - P(B) because B is binary
    # We therefore want to calculate P(A|~B) so we use P(~B|A) (1-0.7) and P(~B|~A) (1-0.4)
    # Calculated using bayes theorum where P(A) = 0.2, P(~B|A) = 1-0.7 (as negative observation), P(~B|notA) = 1-0.4 -> 0.11

    assert state.state == "off"

    hass.states.async_set("sensor.test_monitored", 6)
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_monitored1", 6)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_binary")
    assert state.attributes.get("observations")[0]["prob_given_true"] == 0.7
    assert state.attributes.get("observations")[1]["prob_given_true"] == 0.9
    assert state.attributes.get("observations")[1]["prob_given_false"] == 0.2
    assert abs(state.attributes.get("probability") - 0.663) < 0.01
    # Here we have two positive observations as both are in range. We do a 2-step bayes. The output of the first is used as the (updated) prior in the second.
    # 1st step P(A) = 0.2, P(B|A) = 0.7, P(B|notA) = 0.4 -> 0.304
    # 2nd update: P(A) = 0.304, P(B|A) = 0.9, P(B|notA) = 0.2 -> 0.663

    assert state.state == "on"

    hass.states.async_set("sensor.test_monitored1", 0)
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_monitored", 4)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_binary")
    assert abs(state.attributes.get("probability") - 0.0153) < 0.01
    # Calculated using bayes theorum where P(A) = 0.2, P(~B|A) = 0.3, P(~B|notA) = 0.6 -> 0.11
    # 2nd update: P(A) = 0.111, P(~B|A) = 0.1, P(~B|notA) = 0.8

    assert state.state == "off"

    hass.states.async_set("sensor.test_monitored", 15)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_binary")

    assert state.state == "off"

    assert len(issue_registry.issues) == 0


async def test_sensor_state(hass: HomeAssistant) -> None:
    """Test sensor on state platform observations."""
    prior = 0.2
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
            "prior": prior,
            "probability_threshold": 0.32,
        }
    }

    assert await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()

    hass.states.async_set("sensor.test_monitored", "on")
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test_binary")

    assert state.attributes.get("occurred_observation_entities") == [
        "sensor.test_monitored"
    ]
    assert state.attributes.get("observations")[0]["prob_given_true"] == 0.8
    assert state.attributes.get("observations")[0]["prob_given_false"] == 0.4
    assert abs(0.0769 - state.attributes.get("probability")) < 0.01
    # Calculated using bayes theorum where P(A) = 0.2, P(~B|A) = 0.2 (as negative observation), P(~B|notA) = 0.6
    assert state.state == "off"

    hass.states.async_set("sensor.test_monitored", "off")
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test_binary")

    assert state.attributes.get("occurred_observation_entities") == [
        "sensor.test_monitored"
    ]
    assert abs(0.33 - state.attributes.get("probability")) < 0.01
    # Calculated using bayes theorum where P(A) = 0.2, P(~B|A) = 0.8 (as negative observation), P(~B|notA) = 0.4
    assert state.state == "on"

    hass.states.async_remove("sensor.test_monitored")
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test_binary")

    assert state.attributes.get("occurred_observation_entities") == []
    assert abs(prior - state.attributes.get("probability")) < 0.01
    assert state.state == "off"

    hass.states.async_set("sensor.test_monitored", STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test_binary")

    assert state.attributes.get("occurred_observation_entities") == []
    assert abs(prior - state.attributes.get("probability")) < 0.01
    assert state.state == "off"

    hass.states.async_set("sensor.test_monitored", STATE_UNKNOWN)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test_binary")

    assert state.attributes.get("occurred_observation_entities") == []
    assert abs(prior - state.attributes.get("probability")) < 0.01
    assert state.state == "off"


async def test_sensor_value_template(hass: HomeAssistant) -> None:
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

    assert state.attributes.get("occurred_observation_entities") == []
    assert abs(0.0769 - state.attributes.get("probability")) < 0.01
    # Calculated using bayes theorum where P(A) = 0.2, P(~B|A) = 0.2 (as negative observation), P(~B|notA) = 0.6

    assert state.state == "off"

    hass.states.async_set("sensor.test_monitored", "off")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_binary")
    assert state.attributes.get("observations")[0]["prob_given_true"] == 0.8
    assert state.attributes.get("observations")[0]["prob_given_false"] == 0.4
    assert abs(0.33333 - state.attributes.get("probability")) < 0.01
    # Calculated using bayes theorum where P(A) = 0.2, P(B|A) = 0.8, P(B|notA) = 0.4

    assert state.state == "on"

    hass.states.async_set("sensor.test_monitored", "on")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_binary")
    assert abs(0.076923 - state.attributes.get("probability")) < 0.01
    # Calculated using bayes theorum where P(A) = 0.2, P(~B|A) = 0.2 (as negative observation), P(~B|notA) = 0.6

    assert state.state == "off"


async def test_threshold(hass: HomeAssistant, issue_registry: ir.IssueRegistry) -> None:
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
                    "prob_given_false": 0.0,
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
    assert len(issue_registry.issues) == 0


async def test_multiple_observations(hass: HomeAssistant) -> None:
    """Test sensor with multiple observations of same entity.

    these entries should be labelled as 'multi_state' and negative observations ignored - as the outcome is not known to be binary.
    Before the merge of #67631 this practice was a common work-around for bayesian's ignoring of negative observations,
    this also preserves that function
    """

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
                    "prob_given_false": 0.6,
                },
            ],
            "prior": 0.2,
            "probability_threshold": 0.32,
        }
    }

    assert await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()

    hass.states.async_set("sensor.test_monitored", "off")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_binary")

    for attrs in state.attributes.values():
        json.dumps(attrs)
    assert state.attributes.get("occurred_observation_entities") == []
    assert state.attributes.get("probability") == 0.2
    # probability should be the same as the prior as negative observations are ignored in multi-state

    assert state.state == "off"

    hass.states.async_set("sensor.test_monitored", "blue")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_binary")

    assert state.attributes.get("occurred_observation_entities") == [
        "sensor.test_monitored"
    ]
    assert state.attributes.get("observations")[0]["prob_given_true"] == 0.8
    assert state.attributes.get("observations")[0]["prob_given_false"] == 0.4
    assert round(abs(0.33 - state.attributes.get("probability")), 7) == 0
    # Calculated using bayes theorum where P(A) = 0.2, P(B|A) = 0.8, P(B|notA) = 0.4

    assert state.state == "on"

    hass.states.async_set("sensor.test_monitored", "red")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_binary")
    assert abs(0.076923 - state.attributes.get("probability")) < 0.01
    # Calculated using bayes theorum where P(A) = 0.2, P(B|A) = 0.2, P(B|notA) = 0.6

    assert state.state == "off"
    assert state.attributes.get("observations")[0]["platform"] == "multi_state"
    assert state.attributes.get("observations")[1]["platform"] == "multi_state"


async def test_multiple_numeric_observations(hass: HomeAssistant) -> None:
    """Test sensor with multiple numeric observations of same entity."""

    config = {
        "binary_sensor": {
            "platform": "bayesian",
            "name": "Test_Binary",
            "observations": [
                {
                    "platform": "numeric_state",
                    "entity_id": "sensor.test_monitored",
                    "below": 10,
                    "above": 0,
                    "prob_given_true": 0.4,
                    "prob_given_false": 0.0001,
                },
                {
                    "platform": "numeric_state",
                    "entity_id": "sensor.test_monitored",
                    "below": 100,
                    "above": 30,
                    "prob_given_true": 0.6,
                    "prob_given_false": 0.0001,
                },
            ],
            "prior": 0.1,
        }
    }

    assert await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()

    hass.states.async_set("sensor.test_monitored", STATE_UNKNOWN)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_binary")

    for attrs in state.attributes.values():
        json.dumps(attrs)
    assert state.attributes.get("occurred_observation_entities") == []
    assert state.attributes.get("probability") == 0.1
    # No observations made so probability should be the prior

    assert state.state == "off"

    hass.states.async_set("sensor.test_monitored", 20)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_binary")

    assert state.attributes.get("occurred_observation_entities") == [
        "sensor.test_monitored"
    ]
    assert round(abs(0.026 - state.attributes.get("probability")), 7) < 0.01
    # Step 1 Calculated where P(A) = 0.1, P(~B|A) = 0.6 (negative obs), P(~B|notA) = 0.9999 -> 0.0625
    # Step 2 P(A) = 0.0625, P(B|A) = 0.4 (negative obs), P(B|notA) = 0.9999 -> 0.26

    assert state.state == "off"

    hass.states.async_set("sensor.test_monitored", 35)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_binary")
    assert state.attributes.get("occurred_observation_entities") == [
        "sensor.test_monitored"
    ]
    assert abs(1 - state.attributes.get("probability")) < 0.01
    # Step 1 Calculated where P(A) = 0.1, P(~B|A) = 0.6 (negative obs), P(~B|notA) = 0.9999 -> 0.0625
    # Step 2 P(A) = 0.0625, P(B|A) = 0.6, P(B|notA) = 0.0001 -> 0.9975

    assert state.state == "on"
    assert state.attributes.get("observations")[0]["platform"] == "numeric_state"
    assert state.attributes.get("observations")[1]["platform"] == "numeric_state"


async def test_mirrored_observations(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test whether mirrored entries are detected and appropriate issues are created."""

    config = {
        "binary_sensor": {
            "platform": "bayesian",
            "name": "Test_Binary",
            "observations": [
                {
                    "platform": "state",
                    "entity_id": "binary_sensor.test_monitored",
                    "to_state": "on",
                    "prob_given_true": 0.8,
                    "prob_given_false": 0.4,
                },
                {
                    "platform": "state",
                    "entity_id": "binary_sensor.test_monitored",
                    "to_state": "off",
                    "prob_given_true": 0.2,
                    "prob_given_false": 0.59,
                },
                {
                    "platform": "numeric_state",
                    "entity_id": "sensor.test_monitored1",
                    "above": 5,
                    "prob_given_true": 0.7,
                    "prob_given_false": 0.4,
                },
                {
                    "platform": "numeric_state",
                    "entity_id": "sensor.test_monitored1",
                    "below": 5,
                    "prob_given_true": 0.3,
                    "prob_given_false": 0.6,
                },
                {
                    "platform": "template",
                    "value_template": "{{states('sensor.test_monitored2') == 'off'}}",
                    "prob_given_true": 0.79,
                    "prob_given_false": 0.4,
                },
                {
                    "platform": "template",
                    "value_template": "{{states('sensor.test_monitored2') == 'on'}}",
                    "prob_given_true": 0.2,
                    "prob_given_false": 0.6,
                },
                {
                    "platform": "state",
                    "entity_id": "sensor.colour",
                    "to_state": "blue",
                    "prob_given_true": 0.33,
                    "prob_given_false": 0.8,
                },
                {
                    "platform": "state",
                    "entity_id": "sensor.colour",
                    "to_state": "green",
                    "prob_given_true": 0.3,
                    "prob_given_false": 0.15,
                },
                {
                    "platform": "state",
                    "entity_id": "sensor.colour",
                    "to_state": "red",
                    "prob_given_true": 0.4,
                    "prob_given_false": 0.05,
                },
            ],
            "prior": 0.1,
        }
    }
    assert len(issue_registry.issues) == 0
    assert await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_monitored2", "on")
    await hass.async_block_till_done()

    assert len(issue_registry.issues) == 3
    assert (
        issue_registry.issues[
            ("bayesian", "mirrored_entry/Test_Binary/sensor.test_monitored1")
        ]
        is not None
    )


async def test_missing_prob_given_false(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test whether missing prob_given_false are detected and appropriate issues are created."""

    config = {
        "binary_sensor": {
            "platform": "bayesian",
            "name": "missingpgf",
            "observations": [
                {
                    "platform": "state",
                    "entity_id": "binary_sensor.test_monitored",
                    "to_state": "on",
                    "prob_given_true": 0.8,
                },
                {
                    "platform": "template",
                    "value_template": "{{states('sensor.test_monitored2') == 'off'}}",
                    "prob_given_true": 0.79,
                },
                {
                    "platform": "numeric_state",
                    "entity_id": "sensor.test_monitored1",
                    "above": 5,
                    "prob_given_true": 0.7,
                },
            ],
            "prior": 0.1,
        }
    }
    assert len(issue_registry.issues) == 0
    assert await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_monitored2", "on")
    await hass.async_block_till_done()

    assert len(issue_registry.issues) == 3
    assert (
        issue_registry.issues[
            ("bayesian", "no_prob_given_false/missingpgf/sensor.test_monitored1")
        ]
        is not None
    )


async def test_probability_updates(hass: HomeAssistant) -> None:
    """Test probability update function."""
    prob_given_true = [0.3, 0.6, 0.8]
    prob_given_false = [0.7, 0.4, 0.2]
    prior = 0.5

    for p_t, p_f in zip(prob_given_true, prob_given_false, strict=False):
        prior = bayesian.update_probability(prior, p_t, p_f)

    assert round(abs(0.720000 - prior), 7) == 0

    prob_given_true = [0.8, 0.3, 0.9]
    prob_given_false = [0.6, 0.4, 0.2]
    prior = 0.7

    for p_t, p_f in zip(prob_given_true, prob_given_false, strict=False):
        prior = bayesian.update_probability(prior, p_t, p_f)

    assert round(abs(0.9130434782608695 - prior), 7) == 0


async def test_observed_entities(hass: HomeAssistant) -> None:
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
                    "value_template": (
                        "{{is_state('sensor.test_monitored1','on') and"
                        " is_state('sensor.test_monitored','off')}}"
                    ),
                    "prob_given_true": 0.9,
                    "prob_given_false": 0.1,
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
    assert state.attributes.get("occurred_observation_entities") == [
        "sensor.test_monitored"
    ]

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


async def test_state_attributes_are_serializable(hass: HomeAssistant) -> None:
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
                    "value_template": (
                        "{{is_state('sensor.test_monitored1','on') and"
                        " is_state('sensor.test_monitored','off')}}"
                    ),
                    "prob_given_true": 0.9,
                    "prob_given_false": 0.1,
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
    assert state.attributes.get("occurred_observation_entities") == [
        "sensor.test_monitored"
    ]

    hass.states.async_set("sensor.test_monitored", "off")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_binary")
    assert state.attributes.get("occurred_observation_entities") == [
        "sensor.test_monitored"
    ]

    hass.states.async_set("sensor.test_monitored1", "on")
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.test_binary")
    assert ["sensor.test_monitored", "sensor.test_monitored1"] == sorted(
        state.attributes.get("occurred_observation_entities")
    )

    for attrs in state.attributes.values():
        json.dumps(attrs)


async def test_template_error(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
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
                    "prob_given_false": 0.1,
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


async def test_update_request_with_template(hass: HomeAssistant) -> None:
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


async def test_update_request_without_template(hass: HomeAssistant) -> None:
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


async def test_monitored_sensor_goes_away(hass: HomeAssistant) -> None:
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
    # Calculated using bayes theorum where P(A) = 0.2, P(B|A) = 0.9, P(B|notA) = 0.4 -> 0.36 (>0.32)

    hass.states.async_remove("sensor.test_monitored")

    await hass.async_block_till_done()
    assert (
        hass.states.get("binary_sensor.test_binary").attributes.get("probability")
        == 0.2
    )
    assert hass.states.get("binary_sensor.test_binary").state == "off"


async def test_reload(hass: HomeAssistant) -> None:
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

    yaml_path = get_fixture_path("configuration.yaml", "bayesian")

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


async def test_template_triggers(hass: HomeAssistant) -> None:
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
                    "prob_given_true": 1.0,
                    "prob_given_false": 0.0,
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
    async_track_state_change_event(
        hass, "binary_sensor.test_binary", callback(lambda event: events.append(event))
    )

    context = Context()
    hass.states.async_set("input_boolean.test", STATE_ON, context=context)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    assert events[0].context == context


async def test_state_triggers(hass: HomeAssistant) -> None:
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
                    "prob_given_true": 0.9999,
                    "prob_given_false": 0.9994,
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
    async_track_state_change_event(
        hass, "binary_sensor.test_binary", callback(lambda event: events.append(event))
    )

    context = Context()
    hass.states.async_set("sensor.test_monitored", STATE_ON, context=context)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    assert events[0].context == context
