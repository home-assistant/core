"""Test counter triggers."""

from typing import Any

import pytest

from homeassistant.components.counter import (
    CONF_INITIAL,
    CONF_MAXIMUM,
    CONF_MINIMUM,
    DOMAIN,
)
from homeassistant.const import CONF_ENTITY_ID, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, ServiceCall

from tests.components.common import (
    BasicTriggerStateDescription,
    TriggerStateDescription,
    arm_trigger,
    assert_trigger_behavior_any,
    assert_trigger_behavior_first,
    assert_trigger_behavior_last,
    assert_trigger_gated_by_labs_flag,
    parametrize_target_entities,
    parametrize_trigger_states,
    set_or_remove_state,
    target_entities,
)

BEHAVIOR_AWARE_TRIGGERS = [
    *parametrize_trigger_states(
        trigger="counter.maximum_reached",
        target_states=[("2", {CONF_MAXIMUM: 2})],
        other_states=[("1", {CONF_MAXIMUM: 2})],
    ),
    *parametrize_trigger_states(
        trigger="counter.minimum_reached",
        target_states=[("1", {CONF_MINIMUM: 1})],
        other_states=[("2", {CONF_MINIMUM: 1})],
    ),
    *parametrize_trigger_states(
        trigger="counter.reset",
        target_states=[("2", {CONF_INITIAL: 2})],
        other_states=[("3", {CONF_INITIAL: 2})],
    ),
]


@pytest.fixture
async def target_counters(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple counter entities associated with different targets."""
    return await target_entities(hass, DOMAIN)


@pytest.mark.parametrize(
    "trigger_key",
    [
        "counter.decremented",
        "counter.incremented",
        "counter.maximum_reached",
        "counter.minimum_reached",
        "counter.reset",
    ],
)
async def test_counter_triggers_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, trigger_key: str
) -> None:
    """Test the counter triggers are gated by the labs flag."""
    await assert_trigger_gated_by_labs_flag(hass, caplog, trigger_key)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities(DOMAIN),
)
@pytest.mark.parametrize(
    ("trigger", "states"),
    [
        (
            "counter.decremented",
            [
                {"included_state": {"state": None, "attributes": {}}, "count": 0},
                {"included_state": {"state": "1", "attributes": {}}, "count": 0},
                {
                    "included_state": {"state": STATE_UNAVAILABLE, "attributes": {}},
                    "count": 0,
                },
                {"included_state": {"state": "1", "attributes": {}}, "count": 0},
                {
                    "included_state": {"state": STATE_UNKNOWN, "attributes": {}},
                    "count": 0,
                },
                {"included_state": {"state": "1", "attributes": {}}, "count": 0},
                {"included_state": {"state": "2", "attributes": {}}, "count": 0},
                {"included_state": {"state": "1", "attributes": {}}, "count": 1},
            ],
        ),
        (
            "counter.incremented",
            [
                {"included_state": {"state": None, "attributes": {}}, "count": 0},
                {"included_state": {"state": "2", "attributes": {}}, "count": 0},
                {
                    "included_state": {"state": STATE_UNAVAILABLE, "attributes": {}},
                    "count": 0,
                },
                {"included_state": {"state": "2", "attributes": {}}, "count": 0},
                {
                    "included_state": {"state": STATE_UNKNOWN, "attributes": {}},
                    "count": 0,
                },
                {"included_state": {"state": "2", "attributes": {}}, "count": 0},
                {"included_state": {"state": "1", "attributes": {}}, "count": 0},
                {"included_state": {"state": "2", "attributes": {}}, "count": 1},
            ],
        ),
    ],
)
async def test_counter_state_trigger(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_counters: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    states: list[BasicTriggerStateDescription],
) -> None:
    """Test that the counter decrement and increment triggers fire correctly."""
    other_entity_ids = set(target_counters["included_entities"]) - {entity_id}

    # Set all counters, including the tested one, to the initial state
    for eid in target_counters["included_entities"]:
        set_or_remove_state(hass, eid, states[0]["included_state"])
    await hass.async_block_till_done()

    await arm_trigger(hass, trigger, None, trigger_target_config)

    for state in states[1:]:
        included_state = state["included_state"]
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


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities(DOMAIN),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"), BEHAVIOR_AWARE_TRIGGERS
)
async def test_counter_state_trigger_behavior_any(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_counters: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any] | None,
    states: list[TriggerStateDescription],
) -> None:
    """Test that the counter state trigger fires when any counter state changes to a specific state."""
    await assert_trigger_behavior_any(
        hass,
        service_calls=service_calls,
        target_entities=target_counters,
        trigger_target_config=trigger_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        trigger=trigger,
        trigger_options=trigger_options,
        states=states,
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities(DOMAIN),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"), BEHAVIOR_AWARE_TRIGGERS
)
async def test_counter_state_trigger_behavior_first(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_counters: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the counter state trigger fires when the first counter changes to a specific state."""
    await assert_trigger_behavior_first(
        hass,
        service_calls=service_calls,
        target_entities=target_counters,
        trigger_target_config=trigger_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        trigger=trigger,
        trigger_options=trigger_options,
        states=states,
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities(DOMAIN),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"), BEHAVIOR_AWARE_TRIGGERS
)
async def test_counter_state_trigger_behavior_last(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_counters: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the counter state trigger fires when the last counter changes to a specific state."""
    await assert_trigger_behavior_last(
        hass,
        service_calls=service_calls,
        target_entities=target_counters,
        trigger_target_config=trigger_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        trigger=trigger,
        trigger_options=trigger_options,
        states=states,
    )
