"""Test cover trigger."""

from collections.abc import Generator
from unittest.mock import patch

import pytest

from homeassistant.components.cover import ATTR_CURRENT_POSITION, CoverState
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_LABEL_ID, CONF_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component

from tests.components import (
    StateDescription,
    arm_trigger,
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
async def target_covers(hass: HomeAssistant) -> list[str]:
    """Create multiple cover entities associated with different targets."""
    return await target_entities(hass, "cover")


@pytest.mark.parametrize(
    "trigger_key",
    [
        "cover.awning_opened",
        "cover.blind_opened",
        "cover.curtain_opened",
        "cover.door_opened",
        "cover.garage_opened",
        "cover.gate_opened",
        "cover.shade_opened",
        "cover.shutter_opened",
        "cover.window_opened",
    ],
)
async def test_cover_triggers_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, trigger_key: str
) -> None:
    """Test the cover triggers are gated by the labs flag."""
    await arm_trigger(hass, trigger_key, None, {ATTR_LABEL_ID: "test_label"})
    assert (
        "Unnamed automation failed to setup triggers and has been disabled: Trigger "
        f"'{trigger_key}' requires the experimental 'New triggers and conditions' "
        "feature to be enabled in Home Assistant Labs settings (feature flag: "
        "'new_triggers_conditions')"
    ) in caplog.text


@pytest.mark.usefixtures("enable_experimental_triggers_conditions")
def parametrize_closed_trigger_states(
    trigger: str, device_class: str
) -> list[tuple[str, dict, str, list[StateDescription]]]:
    """Parametrize states and expected service call counts.

    Returns a list of tuples with (trigger, trigger_options,
    list of StateDescription).
    """
    additional_attributes = {ATTR_DEVICE_CLASS: device_class}
    return [
        # Test fully_closed = True
        *(
            (s[0], {"fully_closed": True}, *s[1:])
            for s in parametrize_trigger_states(
                trigger=trigger,
                target_states=[
                    (CoverState.CLOSED, {}),
                    (CoverState.CLOSING, {}),
                    (CoverState.CLOSED, {ATTR_CURRENT_POSITION: 0}),
                    (CoverState.CLOSING, {ATTR_CURRENT_POSITION: 0}),
                ],
                other_states=[
                    (CoverState.OPEN, {}),
                    (CoverState.CLOSED, {ATTR_CURRENT_POSITION: 1}),
                ],
                additional_attributes=additional_attributes,
                trigger_from_none=False,
            )
        ),
        # Test fully_closed = False
        *(
            (s[0], {}, *s[1:])
            for s in parametrize_trigger_states(
                trigger=trigger,
                target_states=[
                    (CoverState.CLOSED, {}),
                    (CoverState.CLOSING, {}),
                    (CoverState.CLOSED, {ATTR_CURRENT_POSITION: 99}),
                    (CoverState.CLOSING, {ATTR_CURRENT_POSITION: 99}),
                ],
                other_states=[
                    (CoverState.OPEN, {}),
                    (CoverState.OPEN, {ATTR_CURRENT_POSITION: 1}),
                ],
                additional_attributes=additional_attributes,
                trigger_from_none=False,
            )
        ),
    ]


def parametrize_opened_trigger_states(
    trigger: str, device_class: str
) -> list[tuple[str, dict, str, list[StateDescription]]]:
    """Parametrize states and expected service call counts.

    Returns a list of tuples with (trigger, trigger_options,
    list of StateDescription).
    """
    additional_attributes = {ATTR_DEVICE_CLASS: device_class}
    return [
        # Test fully_opened = True
        *(
            (s[0], {"fully_opened": True}, *s[1:])
            for s in parametrize_trigger_states(
                trigger=trigger,
                target_states=[
                    (CoverState.OPEN, {}),
                    (CoverState.OPENING, {}),
                    (CoverState.OPEN, {ATTR_CURRENT_POSITION: 100}),
                    (CoverState.OPENING, {ATTR_CURRENT_POSITION: 100}),
                ],
                other_states=[
                    (CoverState.CLOSED, {}),
                    (CoverState.OPEN, {ATTR_CURRENT_POSITION: 0}),
                ],
                additional_attributes=additional_attributes,
                trigger_from_none=False,
            )
        ),
        # Test fully_opened = False
        *(
            (s[0], {}, *s[1:])
            for s in parametrize_trigger_states(
                trigger=trigger,
                target_states=[
                    (CoverState.OPEN, {}),
                    (CoverState.OPENING, {}),
                    (CoverState.OPEN, {ATTR_CURRENT_POSITION: 1}),
                    (CoverState.OPENING, {ATTR_CURRENT_POSITION: 1}),
                ],
                other_states=[
                    (CoverState.CLOSED, {}),
                    (CoverState.CLOSED, {ATTR_CURRENT_POSITION: 0}),
                ],
                additional_attributes=additional_attributes,
                trigger_from_none=False,
            )
        ),
    ]


@pytest.mark.usefixtures("enable_experimental_triggers_conditions")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("cover"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_closed_trigger_states("cover.awning_closed", "awning"),
        *parametrize_closed_trigger_states("cover.blind_closed", "blind"),
        *parametrize_closed_trigger_states("cover.curtain_closed", "curtain"),
        *parametrize_closed_trigger_states("cover.door_closed", "door"),
        *parametrize_closed_trigger_states("cover.garage_closed", "garage"),
        *parametrize_closed_trigger_states("cover.gate_closed", "gate"),
        *parametrize_closed_trigger_states("cover.shade_closed", "shade"),
        *parametrize_closed_trigger_states("cover.shutter_closed", "shutter"),
        *parametrize_closed_trigger_states("cover.window_closed", "window"),
        *parametrize_opened_trigger_states("cover.awning_opened", "awning"),
        *parametrize_opened_trigger_states("cover.blind_opened", "blind"),
        *parametrize_opened_trigger_states("cover.curtain_opened", "curtain"),
        *parametrize_opened_trigger_states("cover.door_opened", "door"),
        *parametrize_opened_trigger_states("cover.garage_opened", "garage"),
        *parametrize_opened_trigger_states("cover.gate_opened", "gate"),
        *parametrize_opened_trigger_states("cover.shade_opened", "shade"),
        *parametrize_opened_trigger_states("cover.shutter_opened", "shutter"),
        *parametrize_opened_trigger_states("cover.window_opened", "window"),
    ],
)
async def test_cover_state_attribute_trigger_behavior_any(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_covers: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict,
    states: list[StateDescription],
) -> None:
    """Test that the cover state trigger fires when any cover state changes to a specific state."""
    await async_setup_component(hass, "cover", {})

    other_entity_ids = set(target_covers) - {entity_id}

    # Set all covers, including the tested cover, to the initial state
    for eid in target_covers:
        set_or_remove_state(hass, eid, states[0])
        await hass.async_block_till_done()

    await arm_trigger(hass, trigger, trigger_options, trigger_target_config)

    for state in states[1:]:
        set_or_remove_state(hass, entity_id, state)
        await hass.async_block_till_done()
        assert len(service_calls) == state["count"]
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()

        # Check if changing other covers also triggers
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, state)
            await hass.async_block_till_done()
        assert len(service_calls) == (entities_in_target - 1) * state["count"]
        service_calls.clear()


@pytest.mark.usefixtures("enable_experimental_triggers_conditions")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("cover"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_closed_trigger_states("cover.awning_closed", "awning"),
        *parametrize_closed_trigger_states("cover.blind_closed", "blind"),
        *parametrize_closed_trigger_states("cover.curtain_closed", "curtain"),
        *parametrize_closed_trigger_states("cover.door_closed", "door"),
        *parametrize_closed_trigger_states("cover.garage_closed", "garage"),
        *parametrize_closed_trigger_states("cover.gate_closed", "gate"),
        *parametrize_closed_trigger_states("cover.shade_closed", "shade"),
        *parametrize_closed_trigger_states("cover.shutter_closed", "shutter"),
        *parametrize_closed_trigger_states("cover.window_closed", "window"),
        *parametrize_opened_trigger_states("cover.awning_opened", "awning"),
        *parametrize_opened_trigger_states("cover.blind_opened", "blind"),
        *parametrize_opened_trigger_states("cover.curtain_opened", "curtain"),
        *parametrize_opened_trigger_states("cover.door_opened", "door"),
        *parametrize_opened_trigger_states("cover.garage_opened", "garage"),
        *parametrize_opened_trigger_states("cover.gate_opened", "gate"),
        *parametrize_opened_trigger_states("cover.shade_opened", "shade"),
        *parametrize_opened_trigger_states("cover.shutter_opened", "shutter"),
        *parametrize_opened_trigger_states("cover.window_opened", "window"),
    ],
)
async def test_cover_state_attribute_trigger_behavior_first(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_covers: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict,
    states: list[StateDescription],
) -> None:
    """Test that the cover state trigger fires when the first cover state changes to a specific state."""
    await async_setup_component(hass, "cover", {})

    other_entity_ids = set(target_covers) - {entity_id}

    # Set all covers, including the tested cover, to the initial state
    for eid in target_covers:
        set_or_remove_state(hass, eid, states[0])
        await hass.async_block_till_done()

    await arm_trigger(
        hass,
        trigger,
        {"behavior": "first"} | trigger_options,
        trigger_target_config,
    )

    for state in states[1:]:
        set_or_remove_state(hass, entity_id, state)
        await hass.async_block_till_done()
        assert len(service_calls) == state["count"]
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()

        # Triggering other covers should not cause the trigger to fire again
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, state)
            await hass.async_block_till_done()
        assert len(service_calls) == 0


@pytest.mark.usefixtures("enable_experimental_triggers_conditions")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("cover"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_closed_trigger_states("cover.awning_closed", "awning"),
        *parametrize_closed_trigger_states("cover.blind_closed", "blind"),
        *parametrize_closed_trigger_states("cover.curtain_closed", "curtain"),
        *parametrize_closed_trigger_states("cover.door_closed", "door"),
        *parametrize_closed_trigger_states("cover.garage_closed", "garage"),
        *parametrize_closed_trigger_states("cover.gate_closed", "gate"),
        *parametrize_closed_trigger_states("cover.shade_closed", "shade"),
        *parametrize_closed_trigger_states("cover.shutter_closed", "shutter"),
        *parametrize_closed_trigger_states("cover.window_closed", "window"),
        *parametrize_opened_trigger_states("cover.awning_opened", "awning"),
        *parametrize_opened_trigger_states("cover.blind_opened", "blind"),
        *parametrize_opened_trigger_states("cover.curtain_opened", "curtain"),
        *parametrize_opened_trigger_states("cover.door_opened", "door"),
        *parametrize_opened_trigger_states("cover.garage_opened", "garage"),
        *parametrize_opened_trigger_states("cover.gate_opened", "gate"),
        *parametrize_opened_trigger_states("cover.shade_opened", "shade"),
        *parametrize_opened_trigger_states("cover.shutter_opened", "shutter"),
        *parametrize_opened_trigger_states("cover.window_opened", "window"),
    ],
)
async def test_cover_state_attribute_trigger_behavior_last(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_covers: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict,
    states: list[StateDescription],
) -> None:
    """Test that the cover state trigger fires when the last cover state changes to a specific state."""
    await async_setup_component(hass, "cover", {})

    other_entity_ids = set(target_covers) - {entity_id}

    # Set all covers, including the tested cover, to the initial state
    for eid in target_covers:
        set_or_remove_state(hass, eid, states[0])
        await hass.async_block_till_done()

    await arm_trigger(
        hass, trigger, {"behavior": "last"} | trigger_options, trigger_target_config
    )

    for state in states[1:]:
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, state)
            await hass.async_block_till_done()
        assert len(service_calls) == 0

        set_or_remove_state(hass, entity_id, state)
        await hass.async_block_till_done()
        assert len(service_calls) == state["count"]
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()
