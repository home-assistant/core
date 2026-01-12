"""Test light conditions."""

from collections.abc import Generator
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components import automation
from homeassistant.const import (
    ATTR_LABEL_ID,
    CONF_CONDITION,
    CONF_OPTIONS,
    CONF_TARGET,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component

from tests.components import (
    ConditionStateDescription,
    parametrize_condition_states,
    parametrize_target_entities,
    set_or_remove_state,
    target_entities,
)


@pytest.fixture(autouse=True, name="stub_blueprint_populate")
def stub_blueprint_populate_autouse(stub_blueprint_populate: None) -> None:
    """Stub copying the blueprints to the config folder."""


@pytest.fixture
async def target_lights(hass: HomeAssistant) -> list[str]:
    """Create multiple light entities associated with different targets."""
    return (await target_entities(hass, "light"))["included"]


@pytest.fixture
async def target_switches(hass: HomeAssistant) -> list[str]:
    """Create multiple switch entities associated with different targets."""
    return (await target_entities(hass, "switch"))["included"]


async def setup_automation_with_light_condition(
    hass: HomeAssistant,
    *,
    condition: str,
    target: dict,
    behavior: str,
) -> None:
    """Set up automation with light state condition."""
    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {
                    CONF_CONDITION: condition,
                    CONF_TARGET: target,
                    CONF_OPTIONS: {"behavior": behavior},
                },
                "action": {
                    "service": "test.automation",
                },
            }
        },
    )


async def has_single_call_after_trigger(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> bool:
    """Check if there is a single service call after the trigger event."""
    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    num_calls = len(service_calls)
    service_calls.clear()
    return num_calls == 1


@pytest.fixture(name="enable_experimental_triggers_conditions")
def enable_experimental_triggers_conditions() -> Generator[None]:
    """Enable experimental triggers and conditions."""
    with patch(
        "homeassistant.components.labs.async_is_preview_feature_enabled",
        return_value=True,
    ):
        yield


@pytest.mark.parametrize(
    "condition",
    [
        "light.is_off",
        "light.is_on",
    ],
)
async def test_light_conditions_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, condition: str
) -> None:
    """Test the light conditions are gated by the labs flag."""
    await setup_automation_with_light_condition(
        hass, condition=condition, target={ATTR_LABEL_ID: "test_label"}, behavior="any"
    )
    assert (
        "Unnamed automation failed to setup conditions and has been disabled: "
        f"Condition '{condition}' requires the experimental 'New triggers and "
        "conditions' feature to be enabled in Home Assistant Labs settings "
        "(feature flag: 'new_triggers_conditions')"
    ) in caplog.text


@pytest.mark.usefixtures("enable_experimental_triggers_conditions")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("light"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states(
            condition="light.is_on",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
        ),
        *parametrize_condition_states(
            condition="light.is_off",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
        ),
    ],
)
async def test_light_state_condition_behavior_any(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_lights: list[str],
    target_switches: list[str],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the light state condition with the 'any' behavior."""
    other_entity_ids = set(target_lights) - {entity_id}

    # Set all lights, including the tested light, to the initial state
    for eid in target_lights:
        set_or_remove_state(hass, eid, states[0]["included"])
        await hass.async_block_till_done()

    await setup_automation_with_light_condition(
        hass,
        condition=condition,
        target=condition_target_config,
        behavior="any",
    )

    # Set state for switches to ensure that they don't impact the condition
    for state in states:
        for eid in target_switches:
            set_or_remove_state(hass, eid, state["included"])
        await hass.async_block_till_done()
        assert not await has_single_call_after_trigger(hass, service_calls)

    for state in states:
        included_state = state["included"]
        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert (
            await has_single_call_after_trigger(hass, service_calls)
            == state["condition_true"]
        )

        # Check if changing other lights also passes the condition
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert (
            await has_single_call_after_trigger(hass, service_calls)
            == state["condition_true"]
        )


@pytest.mark.usefixtures("enable_experimental_triggers_conditions")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("light"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states(
            condition="light.is_on",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
        ),
        *parametrize_condition_states(
            condition="light.is_off",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
        ),
    ],
)
async def test_light_state_condition_behavior_all(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_lights: list[str],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the light state condition with the 'all' behavior."""
    # Set state for two switches to ensure that they don't impact the condition
    hass.states.async_set("switch.label_switch_1", STATE_OFF)
    hass.states.async_set("switch.label_switch_2", STATE_ON)

    other_entity_ids = set(target_lights) - {entity_id}

    # Set all lights, including the tested light, to the initial state
    for eid in target_lights:
        set_or_remove_state(hass, eid, states[0]["included"])
        await hass.async_block_till_done()

    await setup_automation_with_light_condition(
        hass,
        condition=condition,
        target=condition_target_config,
        behavior="all",
    )

    for state in states:
        included_state = state["included"]

        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        # The condition passes if all entities are either in a target state or invalid
        assert await has_single_call_after_trigger(hass, service_calls) == (
            (not state["state_valid"])
            or (state["condition_true"] if entities_in_target == 1 else 0)
        )

        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()

        # The condition passes if all entities are either in a target state or invalid
        assert await has_single_call_after_trigger(hass, service_calls) == (
            (not state["state_valid"]) or state["condition_true"]
        )
