"""Test vacuum triggers."""

from collections.abc import Generator
from unittest.mock import patch

import pytest

from homeassistant.components.vacuum import VacuumActivity
from homeassistant.const import ATTR_LABEL_ID, CONF_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component

from tests.components import (
    StateDescription,
    arm_trigger,
    other_states,
    parametrize_target_entities,
    parametrize_trigger_states,
    set_or_remove_state,
    target_entities,
)


@pytest.fixture(autouse=True, name="stub_blueprint_populate")
def stub_blueprint_populate_autouse(stub_blueprint_populate: None) -> None:
    """Stub copying the blueprints to the config folder."""


@pytest.fixture(name="enable_experimental_triggers_conditions")
def enable_experimental_triggers_conditions() -> Generator[None]:
    """Enable experimental triggers and conditions."""
    with patch(
        "homeassistant.components.labs.async_is_preview_feature_enabled",
        return_value=True,
    ):
        yield


@pytest.fixture
async def target_vacuums(hass: HomeAssistant) -> list[str]:
    """Create multiple vacuum entities associated with different targets."""
    return (await target_entities(hass, "vacuum"))["included"]


@pytest.mark.parametrize(
    "trigger_key",
    [
        "vacuum.docked",
        "vacuum.errored",
        "vacuum.paused_cleaning",
        "vacuum.started_cleaning",
    ],
)
async def test_vacuum_triggers_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, trigger_key: str
) -> None:
    """Test the vacuum triggers are gated by the labs flag."""
    await arm_trigger(hass, trigger_key, None, {ATTR_LABEL_ID: "test_label"})
    assert (
        "Unnamed automation failed to setup triggers and has been disabled: Trigger "
        f"'{trigger_key}' requires the experimental 'New triggers and conditions' "
        "feature to be enabled in Home Assistant Labs settings (feature flag: "
        "'new_triggers_conditions')"
    ) in caplog.text


@pytest.mark.usefixtures("enable_experimental_triggers_conditions")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("vacuum"),
)
@pytest.mark.parametrize(
    ("trigger", "states"),
    [
        *parametrize_trigger_states(
            trigger="vacuum.docked",
            target_states=[VacuumActivity.DOCKED],
            other_states=other_states(VacuumActivity.DOCKED),
        ),
        *parametrize_trigger_states(
            trigger="vacuum.errored",
            target_states=[VacuumActivity.ERROR],
            other_states=other_states(VacuumActivity.ERROR),
        ),
        *parametrize_trigger_states(
            trigger="vacuum.paused_cleaning",
            target_states=[VacuumActivity.PAUSED],
            other_states=other_states(VacuumActivity.PAUSED),
        ),
        *parametrize_trigger_states(
            trigger="vacuum.started_cleaning",
            target_states=[VacuumActivity.CLEANING],
            other_states=other_states(VacuumActivity.CLEANING),
        ),
    ],
)
async def test_vacuum_state_trigger_behavior_any(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_vacuums: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    states: list[StateDescription],
) -> None:
    """Test that the vacuum state trigger fires when any vacuum state changes to a specific state."""
    await async_setup_component(hass, "vacuum", {})

    other_entity_ids = set(target_vacuums) - {entity_id}

    # Set all vacuums, including the tested one, to the initial state
    for eid in target_vacuums:
        set_or_remove_state(hass, eid, states[0]["included"])
        await hass.async_block_till_done()

    await arm_trigger(hass, trigger, {}, trigger_target_config)

    for state in states[1:]:
        included_state = state["included"]
        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert len(service_calls) == state["count"]
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()

        # Check if changing other vacuums also triggers
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert len(service_calls) == (entities_in_target - 1) * state["count"]
        service_calls.clear()


@pytest.mark.usefixtures("enable_experimental_triggers_conditions")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("vacuum"),
)
@pytest.mark.parametrize(
    ("trigger", "states"),
    [
        *parametrize_trigger_states(
            trigger="vacuum.docked",
            target_states=[VacuumActivity.DOCKED],
            other_states=other_states(VacuumActivity.DOCKED),
        ),
        *parametrize_trigger_states(
            trigger="vacuum.errored",
            target_states=[VacuumActivity.ERROR],
            other_states=other_states(VacuumActivity.ERROR),
        ),
        *parametrize_trigger_states(
            trigger="vacuum.paused_cleaning",
            target_states=[VacuumActivity.PAUSED],
            other_states=other_states(VacuumActivity.PAUSED),
        ),
        *parametrize_trigger_states(
            trigger="vacuum.started_cleaning",
            target_states=[VacuumActivity.CLEANING],
            other_states=other_states(VacuumActivity.CLEANING),
        ),
    ],
)
async def test_vacuum_state_trigger_behavior_first(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_vacuums: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    states: list[StateDescription],
) -> None:
    """Test that the vacuum state trigger fires when the first vacuum changes to a specific state."""
    await async_setup_component(hass, "vacuum", {})

    other_entity_ids = set(target_vacuums) - {entity_id}

    # Set all vacuums, including the tested one, to the initial state
    for eid in target_vacuums:
        set_or_remove_state(hass, eid, states[0]["included"])
        await hass.async_block_till_done()

    await arm_trigger(hass, trigger, {"behavior": "first"}, trigger_target_config)

    for state in states[1:]:
        included_state = state["included"]
        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert len(service_calls) == state["count"]
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()

        # Triggering other vacuums should not cause the trigger to fire again
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert len(service_calls) == 0


@pytest.mark.usefixtures("enable_experimental_triggers_conditions")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("vacuum"),
)
@pytest.mark.parametrize(
    ("trigger", "states"),
    [
        *parametrize_trigger_states(
            trigger="vacuum.docked",
            target_states=[VacuumActivity.DOCKED],
            other_states=other_states(VacuumActivity.DOCKED),
        ),
        *parametrize_trigger_states(
            trigger="vacuum.errored",
            target_states=[VacuumActivity.ERROR],
            other_states=other_states(VacuumActivity.ERROR),
        ),
        *parametrize_trigger_states(
            trigger="vacuum.paused_cleaning",
            target_states=[VacuumActivity.PAUSED],
            other_states=other_states(VacuumActivity.PAUSED),
        ),
        *parametrize_trigger_states(
            trigger="vacuum.started_cleaning",
            target_states=[VacuumActivity.CLEANING],
            other_states=other_states(VacuumActivity.CLEANING),
        ),
    ],
)
async def test_vacuum_state_trigger_behavior_last(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_vacuums: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    states: list[StateDescription],
) -> None:
    """Test that the vacuum state trigger fires when the last vacuum changes to a specific state."""
    await async_setup_component(hass, "vacuum", {})

    other_entity_ids = set(target_vacuums) - {entity_id}

    # Set all vacuums, including the tested one, to the initial state
    for eid in target_vacuums:
        set_or_remove_state(hass, eid, states[0]["included"])
        await hass.async_block_till_done()

    await arm_trigger(hass, trigger, {"behavior": "last"}, trigger_target_config)

    for state in states[1:]:
        included_state = state["included"]
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert len(service_calls) == 0

        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert len(service_calls) == state["count"]
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()
