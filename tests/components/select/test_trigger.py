"""Test select trigger."""

import pytest

from homeassistant.const import (
    ATTR_LABEL_ID,
    CONF_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, ServiceCall

from tests.components import (
    TriggerStateDescription,
    arm_trigger,
    parametrize_target_entities,
    set_or_remove_state,
    target_entities,
)


@pytest.fixture
async def target_selects(hass: HomeAssistant) -> list[str]:
    """Create multiple select entities associated with different targets."""
    return (await target_entities(hass, "select"))["included"]


@pytest.fixture
async def target_input_selects(hass: HomeAssistant) -> list[str]:
    """Create multiple input_select entities associated with different targets."""
    return (await target_entities(hass, "input_select"))["included"]


@pytest.mark.parametrize("trigger_key", ["select.selection_changed"])
async def test_select_triggers_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, trigger_key: str
) -> None:
    """Test the select triggers are gated by the labs flag."""
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
    parametrize_target_entities("select"),
)
@pytest.mark.parametrize(
    ("trigger", "states"),
    [
        (
            "select.selection_changed",
            [
                {"included": {"state": None, "attributes": {}}, "count": 0},
                {"included": {"state": "option_a", "attributes": {}}, "count": 0},
                {"included": {"state": "option_b", "attributes": {}}, "count": 1},
            ],
        ),
        (
            "select.selection_changed",
            [
                {"included": {"state": "option_a", "attributes": {}}, "count": 0},
                {"included": {"state": "option_b", "attributes": {}}, "count": 1},
                {"included": {"state": "option_c", "attributes": {}}, "count": 1},
            ],
        ),
        (
            "select.selection_changed",
            [
                {
                    "included": {"state": STATE_UNAVAILABLE, "attributes": {}},
                    "count": 0,
                },
                {"included": {"state": "option_a", "attributes": {}}, "count": 0},
                {"included": {"state": "option_b", "attributes": {}}, "count": 1},
                {
                    "included": {"state": STATE_UNAVAILABLE, "attributes": {}},
                    "count": 0,
                },
            ],
        ),
        (
            "select.selection_changed",
            [
                {"included": {"state": STATE_UNKNOWN, "attributes": {}}, "count": 0},
                {"included": {"state": "option_a", "attributes": {}}, "count": 0},
                {"included": {"state": "option_b", "attributes": {}}, "count": 1},
                {"included": {"state": STATE_UNKNOWN, "attributes": {}}, "count": 0},
            ],
        ),
    ],
)
async def test_select_state_trigger_behavior_any(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_selects: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    states: list[TriggerStateDescription],
) -> None:
    """Test that the select trigger fires when any select state changes."""
    other_entity_ids = set(target_selects) - {entity_id}

    # Set all selects, including the tested select, to the initial state
    for eid in target_selects:
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

        # Check if changing other selects also triggers
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert len(service_calls) == (entities_in_target - 1) * state["count"]
        service_calls.clear()


# --- input_select tests ---


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("input_select"),
)
@pytest.mark.parametrize(
    ("trigger", "states"),
    [
        (
            "select.selection_changed",
            [
                {"included": {"state": None, "attributes": {}}, "count": 0},
                {"included": {"state": "option_a", "attributes": {}}, "count": 0},
                {"included": {"state": "option_b", "attributes": {}}, "count": 1},
            ],
        ),
        (
            "select.selection_changed",
            [
                {"included": {"state": "option_a", "attributes": {}}, "count": 0},
                {"included": {"state": "option_b", "attributes": {}}, "count": 1},
                {"included": {"state": "option_c", "attributes": {}}, "count": 1},
            ],
        ),
        (
            "select.selection_changed",
            [
                {
                    "included": {"state": STATE_UNAVAILABLE, "attributes": {}},
                    "count": 0,
                },
                {"included": {"state": "option_a", "attributes": {}}, "count": 0},
                {"included": {"state": "option_b", "attributes": {}}, "count": 1},
                {
                    "included": {"state": STATE_UNAVAILABLE, "attributes": {}},
                    "count": 0,
                },
            ],
        ),
        (
            "select.selection_changed",
            [
                {"included": {"state": STATE_UNKNOWN, "attributes": {}}, "count": 0},
                {"included": {"state": "option_a", "attributes": {}}, "count": 0},
                {"included": {"state": "option_b", "attributes": {}}, "count": 1},
                {"included": {"state": STATE_UNKNOWN, "attributes": {}}, "count": 0},
            ],
        ),
    ],
)
async def test_input_select_state_trigger_behavior_any(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_input_selects: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    states: list[TriggerStateDescription],
) -> None:
    """Test that the select trigger fires when any input_select state changes."""
    other_entity_ids = set(target_input_selects) - {entity_id}

    # Set all input_selects to the initial state
    for eid in target_input_selects:
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

        # Check if changing other input_selects also triggers
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert len(service_calls) == (entities_in_target - 1) * state["count"]
        service_calls.clear()


# --- Cross-domain test ---


@pytest.mark.usefixtures("enable_labs_preview_features")
async def test_select_trigger_fires_for_both_domains(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
) -> None:
    """Test that the select trigger fires for both select and input_select entities."""
    entity_id_select = "select.test_select"
    entity_id_input_select = "input_select.test_input_select"

    hass.states.async_set(entity_id_select, "option_a")
    hass.states.async_set(entity_id_input_select, "option_a")
    await hass.async_block_till_done()

    await arm_trigger(
        hass,
        "select.selection_changed",
        None,
        {CONF_ENTITY_ID: [entity_id_select, entity_id_input_select]},
    )

    # select entity changes - should trigger
    hass.states.async_set(entity_id_select, "option_b")
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_id_select
    service_calls.clear()

    # input_select entity changes - should also trigger
    hass.states.async_set(entity_id_input_select, "option_b")
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_id_input_select
    service_calls.clear()
