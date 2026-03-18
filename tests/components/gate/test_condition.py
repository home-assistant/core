"""Test gate conditions."""

from typing import Any

import pytest

from homeassistant.components.cover import ATTR_IS_CLOSED, CoverState
from homeassistant.const import ATTR_DEVICE_CLASS, CONF_ENTITY_ID
from homeassistant.core import HomeAssistant

from tests.components.common import (
    ConditionStateDescription,
    assert_condition_behavior_all,
    assert_condition_behavior_any,
    assert_condition_gated_by_labs_flag,
    create_target_condition,
    parametrize_condition_states_all,
    parametrize_condition_states_any,
    parametrize_target_entities,
    target_entities,
)


@pytest.fixture
async def target_covers(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple cover entities associated with different targets."""
    return await target_entities(hass, "cover")


@pytest.mark.parametrize(
    "condition",
    [
        "gate.is_closed",
        "gate.is_open",
    ],
)
async def test_gate_conditions_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, condition: str
) -> None:
    """Test the gate conditions are gated by the labs flag."""
    await assert_condition_gated_by_labs_flag(hass, caplog, condition)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("cover"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_any(
            condition="gate.is_open",
            target_states=[
                (CoverState.OPEN, {ATTR_IS_CLOSED: False}),
                (CoverState.OPENING, {ATTR_IS_CLOSED: False}),
                (CoverState.CLOSING, {ATTR_IS_CLOSED: False}),
            ],
            other_states=[
                (CoverState.CLOSED, {ATTR_IS_CLOSED: True}),
                (CoverState.CLOSING, {ATTR_IS_CLOSED: True}),
            ],
            required_filter_attributes={ATTR_DEVICE_CLASS: "gate"},
        ),
        *parametrize_condition_states_any(
            condition="gate.is_closed",
            target_states=[
                (CoverState.CLOSED, {ATTR_IS_CLOSED: True}),
                (CoverState.CLOSING, {ATTR_IS_CLOSED: True}),
            ],
            other_states=[
                (CoverState.OPEN, {ATTR_IS_CLOSED: False}),
                (CoverState.OPENING, {ATTR_IS_CLOSED: False}),
                (CoverState.CLOSING, {ATTR_IS_CLOSED: False}),
            ],
            required_filter_attributes={ATTR_DEVICE_CLASS: "gate"},
        ),
    ],
)
async def test_gate_cover_condition_behavior_any(
    hass: HomeAssistant,
    target_covers: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test gate condition for cover entities with 'any' behavior."""
    await assert_condition_behavior_any(
        hass,
        target_entities=target_covers,
        condition_target_config=condition_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        condition=condition,
        condition_options=condition_options,
        states=states,
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("cover"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_all(
            condition="gate.is_open",
            target_states=[
                (CoverState.OPEN, {ATTR_IS_CLOSED: False}),
                (CoverState.OPENING, {ATTR_IS_CLOSED: False}),
                (CoverState.CLOSING, {ATTR_IS_CLOSED: False}),
            ],
            other_states=[
                (CoverState.CLOSED, {ATTR_IS_CLOSED: True}),
                (CoverState.CLOSING, {ATTR_IS_CLOSED: True}),
            ],
            required_filter_attributes={ATTR_DEVICE_CLASS: "gate"},
        ),
        *parametrize_condition_states_all(
            condition="gate.is_closed",
            target_states=[
                (CoverState.CLOSED, {ATTR_IS_CLOSED: True}),
                (CoverState.CLOSING, {ATTR_IS_CLOSED: True}),
            ],
            other_states=[
                (CoverState.OPEN, {ATTR_IS_CLOSED: False}),
                (CoverState.OPENING, {ATTR_IS_CLOSED: False}),
                (CoverState.CLOSING, {ATTR_IS_CLOSED: False}),
            ],
            required_filter_attributes={ATTR_DEVICE_CLASS: "gate"},
        ),
    ],
)
async def test_gate_cover_condition_behavior_all(
    hass: HomeAssistant,
    target_covers: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test gate condition for cover entities with 'all' behavior."""
    await assert_condition_behavior_all(
        hass,
        target_entities=target_covers,
        condition_target_config=condition_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        condition=condition,
        condition_options=condition_options,
        states=states,
    )


# --- Device class exclusion test ---


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    (
        "condition_key",
        "cover_matching",
        "cover_matching_is_closed",
        "cover_non_matching",
        "cover_non_matching_is_closed",
    ),
    [
        (
            "gate.is_open",
            CoverState.OPEN,
            False,
            CoverState.CLOSED,
            True,
        ),
        (
            "gate.is_closed",
            CoverState.CLOSED,
            True,
            CoverState.OPEN,
            False,
        ),
    ],
)
async def test_gate_condition_excludes_non_gate_device_class(
    hass: HomeAssistant,
    condition_key: str,
    cover_matching: str,
    cover_matching_is_closed: bool,
    cover_non_matching: str,
    cover_non_matching_is_closed: bool,
) -> None:
    """Test gate condition excludes entities without device_class gate."""
    entity_id_gate = "cover.test_gate"
    entity_id_door = "cover.test_door"

    # Set matching states on all entities
    hass.states.async_set(
        entity_id_gate,
        cover_matching,
        {ATTR_DEVICE_CLASS: "gate", ATTR_IS_CLOSED: cover_matching_is_closed},
    )
    hass.states.async_set(
        entity_id_door,
        cover_matching,
        {ATTR_DEVICE_CLASS: "door", ATTR_IS_CLOSED: cover_matching_is_closed},
    )
    await hass.async_block_till_done()

    condition_any = await create_target_condition(
        hass,
        condition=condition_key,
        target={CONF_ENTITY_ID: [entity_id_gate, entity_id_door]},
        behavior="any",
    )

    # Matching entity in matching state - condition should be True
    assert condition_any(hass) is True

    # Set matching entity to non-matching state
    hass.states.async_set(
        entity_id_gate,
        cover_non_matching,
        {ATTR_DEVICE_CLASS: "gate", ATTR_IS_CLOSED: cover_non_matching_is_closed},
    )
    await hass.async_block_till_done()

    # Wrong device class entity still in matching state, but should be excluded
    assert condition_any(hass) is False
