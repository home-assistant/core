"""Test counter triggers."""

from typing import Any

import pytest

from homeassistant.components.counter import (
    ATTR_STEP,
    CONF_INITIAL,
    CONF_MAXIMUM,
    CONF_MINIMUM,
    DOMAIN,
)
from homeassistant.const import ATTR_LABEL_ID, CONF_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall

from tests.components import (
    TriggerStateDescription,
    arm_trigger,
    parametrize_target_entities,
    parametrize_trigger_states,
    set_or_remove_state,
    target_entities,
)


@pytest.fixture
async def target_counters(hass: HomeAssistant) -> list[str]:
    """Create multiple counter entities associated with different targets."""
    return (await target_entities(hass, DOMAIN))["included"]


@pytest.mark.parametrize(
    "trigger_key",
    [
        "counter.decremented",
        "counter.incremented",
        "counter.maximum_reached",
        "counter.reset",
    ],
)
async def test_counter_triggers_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, trigger_key: str
) -> None:
    """Test the counter triggers are gated by the labs flag."""
    await arm_trigger(hass, trigger_key, None, {ATTR_LABEL_ID: "test_label"})
    assert (
        "Unnamed automation failed to setup triggers and has been disabled: Trigger "
        f"'{trigger_key}' requires the experimental 'New triggers and conditions' "
        "feature to be enabled in Home Assistant Labs settings (feature flag: "
        "'new_triggers_conditions')"
    ) in caplog.text


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities(DOMAIN),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="counter.decremented",
            target_states=[("1", {ATTR_STEP: 1})],
            other_states=[("2", {ATTR_STEP: 1})],
        ),
        (
            "counter.decremented",
            {},
            [
                {"included": {"state": None, "attributes": {ATTR_STEP: 3}}, "count": 0},
                {
                    # not triggered as no from state
                    "included": {"state": "10", "attributes": {ATTR_STEP: 3}},
                    "count": 0,
                },
                {
                    # not triggered as delta is not setp size of 3
                    "included": {"state": "9", "attributes": {ATTR_STEP: 3}},
                    "count": 0,
                },
                {
                    # not triggered as delta is not step size of 3
                    "included": {"state": "5", "attributes": {ATTR_STEP: 3}},
                    "count": 0,
                },
                {
                    # triggered as delta is setp size of 3
                    "included": {"state": "2", "attributes": {ATTR_STEP: 3}},
                    "count": 1,
                },
                {
                    # triggered as delta is lower than step size of 3 but new state is minimum value
                    "included": {
                        "state": "0",
                        "attributes": {ATTR_STEP: 3, CONF_MINIMUM: 0},
                    },
                    "count": 1,
                },
            ],
        ),
        *parametrize_trigger_states(
            trigger="counter.incremented",
            target_states=[("2", {ATTR_STEP: 1})],
            other_states=[("1", {ATTR_STEP: 1})],
        ),
        (
            "counter.incremented",
            {},
            [
                {"included": {"state": None, "attributes": {ATTR_STEP: 3}}, "count": 0},
                {
                    # not triggered as no from state
                    "included": {"state": "1", "attributes": {ATTR_STEP: 3}},
                    "count": 0,
                },
                {
                    # not triggered as delta is not setp size of 3
                    "included": {"state": "2", "attributes": {ATTR_STEP: 3}},
                    "count": 0,
                },
                {
                    # not triggered as delta is not step size of 3
                    "included": {"state": "4", "attributes": {ATTR_STEP: 3}},
                    "count": 0,
                },
                {
                    # triggered as delta is setp size of 3
                    "included": {"state": "7", "attributes": {ATTR_STEP: 3}},
                    "count": 1,
                },
                {
                    # triggered as delta is lower than step size of 3 but new state is maximum value
                    "included": {
                        "state": "9",
                        "attributes": {ATTR_STEP: 3, CONF_MAXIMUM: 9},
                    },
                    "count": 1,
                },
            ],
        ),
        *parametrize_trigger_states(
            trigger="counter.maximum_reached",
            target_states=[("2", {CONF_MAXIMUM: 2})],
            other_states=[("1", {CONF_MAXIMUM: 2})],
        ),
        (
            "counter.maximum_reached",
            {},
            [
                {"included": {"state": None, "attributes": {}}, "count": 0},
                {"included": {"state": "1", "attributes": {}}, "count": 0},
                {"included": {"state": None, "attributes": {}}, "count": 0},
            ],
        ),
        *parametrize_trigger_states(
            trigger="counter.reset",
            target_states=[("2", {CONF_INITIAL: 2})],
            other_states=[("3", {CONF_INITIAL: 2})],
        ),
    ],
)
async def test_counter_state_trigger_behavior(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_counters: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the counter state trigger fires when any counter state changes to a specific state."""
    other_entity_ids = set(target_counters) - {entity_id}

    # Set all counters, including the tested one, to the initial state
    for eid in target_counters:
        set_or_remove_state(hass, eid, states[0]["included"])
        await hass.async_block_till_done()

    await arm_trigger(hass, trigger, None, trigger_target_config)

    for state in states[1:]:
        included_state = state["included"]
        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert len(service_calls) == state["count"]
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()

        # Check if changing other counters also triggers
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert len(service_calls) == (entities_in_target - 1) * state["count"]
        service_calls.clear()
