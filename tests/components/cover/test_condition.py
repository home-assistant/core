"""Test cover conditions."""

from typing import Any

import pytest

from homeassistant.components.cover import ATTR_IS_CLOSED, CoverState
from homeassistant.const import ATTR_DEVICE_CLASS, CONF_ENTITY_ID
from homeassistant.core import HomeAssistant

from tests.components.common import (
    ConditionStateDescription,
    assert_condition_gated_by_labs_flag,
    create_target_condition,
    parametrize_condition_states_all,
    parametrize_condition_states_any,
    parametrize_target_entities,
    set_or_remove_state,
    target_entities,
)

DEVICE_CLASS_CONDITIONS = [
    ("awning", "cover.awning_is_open", "cover.awning_is_closed"),
    ("blind", "cover.blind_is_open", "cover.blind_is_closed"),
    ("curtain", "cover.curtain_is_open", "cover.curtain_is_closed"),
    ("shade", "cover.shade_is_open", "cover.shade_is_closed"),
    ("shutter", "cover.shutter_is_open", "cover.shutter_is_closed"),
]


@pytest.fixture
async def target_covers(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple cover entities associated with different targets."""
    return await target_entities(hass, "cover")


@pytest.mark.parametrize(
    "condition",
    [
        condition
        for _, is_open, is_closed in DEVICE_CLASS_CONDITIONS
        for condition in (is_open, is_closed)
    ],
)
async def test_cover_conditions_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, condition: str
) -> None:
    """Test the cover conditions are gated by the labs flag."""
    await assert_condition_gated_by_labs_flag(hass, caplog, condition)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("cover"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        param
        for device_class, is_open_key, is_closed_key in DEVICE_CLASS_CONDITIONS
        for param in (
            *parametrize_condition_states_any(
                condition=is_open_key,
                target_states=[
                    (CoverState.OPEN, {ATTR_IS_CLOSED: False}),
                    (CoverState.OPENING, {ATTR_IS_CLOSED: False}),
                    (CoverState.CLOSING, {ATTR_IS_CLOSED: False}),
                ],
                other_states=[
                    (CoverState.CLOSED, {ATTR_IS_CLOSED: True}),
                    (CoverState.CLOSING, {ATTR_IS_CLOSED: True}),
                ],
                additional_attributes={ATTR_DEVICE_CLASS: device_class},
            ),
            *parametrize_condition_states_any(
                condition=is_closed_key,
                target_states=[
                    (CoverState.CLOSED, {ATTR_IS_CLOSED: True}),
                    (CoverState.CLOSING, {ATTR_IS_CLOSED: True}),
                ],
                other_states=[
                    (CoverState.OPEN, {ATTR_IS_CLOSED: False}),
                    (CoverState.OPENING, {ATTR_IS_CLOSED: False}),
                    (CoverState.CLOSING, {ATTR_IS_CLOSED: False}),
                ],
                additional_attributes={ATTR_DEVICE_CLASS: device_class},
            ),
        )
    ],
)
async def test_cover_condition_behavior_any(
    hass: HomeAssistant,
    target_covers: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test cover condition with the 'any' behavior."""
    other_entity_ids = set(target_covers["included"]) - {entity_id}
    excluded_entity_ids = set(target_covers["excluded"]) - {entity_id}

    for eid in target_covers["included"]:
        set_or_remove_state(hass, eid, states[0]["included"])
        await hass.async_block_till_done()
    for eid in excluded_entity_ids:
        set_or_remove_state(hass, eid, states[0]["excluded"])
        await hass.async_block_till_done()

    condition = await create_target_condition(
        hass,
        condition=condition,
        target=condition_target_config,
        behavior="any",
    )

    for state in states:
        included_state = state["included"]
        excluded_state = state["excluded"]
        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert condition(hass) == state["condition_true"]

        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        for excluded_entity_id in excluded_entity_ids:
            set_or_remove_state(hass, excluded_entity_id, excluded_state)
            await hass.async_block_till_done()
        assert condition(hass) == state["condition_true"]


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("cover"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        param
        for device_class, is_open_key, is_closed_key in DEVICE_CLASS_CONDITIONS
        for param in (
            *parametrize_condition_states_all(
                condition=is_open_key,
                target_states=[
                    (CoverState.OPEN, {ATTR_IS_CLOSED: False}),
                    (CoverState.OPENING, {ATTR_IS_CLOSED: False}),
                    (CoverState.CLOSING, {ATTR_IS_CLOSED: False}),
                ],
                other_states=[
                    (CoverState.CLOSED, {ATTR_IS_CLOSED: True}),
                    (CoverState.CLOSING, {ATTR_IS_CLOSED: True}),
                ],
                additional_attributes={ATTR_DEVICE_CLASS: device_class},
            ),
            *parametrize_condition_states_all(
                condition=is_closed_key,
                target_states=[
                    (CoverState.CLOSED, {ATTR_IS_CLOSED: True}),
                    (CoverState.CLOSING, {ATTR_IS_CLOSED: True}),
                ],
                other_states=[
                    (CoverState.OPEN, {ATTR_IS_CLOSED: False}),
                    (CoverState.OPENING, {ATTR_IS_CLOSED: False}),
                    (CoverState.CLOSING, {ATTR_IS_CLOSED: False}),
                ],
                additional_attributes={ATTR_DEVICE_CLASS: device_class},
            ),
        )
    ],
)
async def test_cover_condition_behavior_all(
    hass: HomeAssistant,
    target_covers: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test cover condition with the 'all' behavior."""
    other_entity_ids = set(target_covers["included"]) - {entity_id}
    excluded_entity_ids = set(target_covers["excluded"]) - {entity_id}

    for eid in target_covers["included"]:
        set_or_remove_state(hass, eid, states[0]["included"])
        await hass.async_block_till_done()
    for eid in excluded_entity_ids:
        set_or_remove_state(hass, eid, states[0]["excluded"])
        await hass.async_block_till_done()

    condition = await create_target_condition(
        hass,
        condition=condition,
        target=condition_target_config,
        behavior="all",
    )

    for state in states:
        included_state = state["included"]
        excluded_state = state["excluded"]

        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert condition(hass) == state["condition_true_first_entity"]

        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        for excluded_entity_id in excluded_entity_ids:
            set_or_remove_state(hass, excluded_entity_id, excluded_state)
            await hass.async_block_till_done()

        assert condition(hass) == state["condition_true"]


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    (
        "condition_key",
        "device_class",
        "wrong_device_class",
        "matching_state",
        "matching_is_closed",
        "non_matching_state",
        "non_matching_is_closed",
    ),
    [
        (
            is_open_key,
            device_class,
            "damper",
            CoverState.OPEN,
            False,
            CoverState.CLOSED,
            True,
        )
        for device_class, is_open_key, _ in DEVICE_CLASS_CONDITIONS
    ]
    + [
        (
            is_closed_key,
            device_class,
            "damper",
            CoverState.CLOSED,
            True,
            CoverState.OPEN,
            False,
        )
        for device_class, _, is_closed_key in DEVICE_CLASS_CONDITIONS
    ],
)
async def test_cover_condition_excludes_non_matching_device_class(
    hass: HomeAssistant,
    condition_key: str,
    device_class: str,
    wrong_device_class: str,
    matching_state: str,
    matching_is_closed: bool,
    non_matching_state: str,
    non_matching_is_closed: bool,
) -> None:
    """Test cover condition excludes entities without matching device_class."""
    entity_id_matching = "cover.test_matching"
    entity_id_wrong = "cover.test_wrong"

    # Set matching entity to matching state
    hass.states.async_set(
        entity_id_matching,
        matching_state,
        {ATTR_DEVICE_CLASS: device_class, ATTR_IS_CLOSED: matching_is_closed},
    )
    # Set wrong device class entity to matching state too
    hass.states.async_set(
        entity_id_wrong,
        matching_state,
        {
            ATTR_DEVICE_CLASS: wrong_device_class,
            ATTR_IS_CLOSED: matching_is_closed,
        },
    )
    await hass.async_block_till_done()

    condition_any = await create_target_condition(
        hass,
        condition=condition_key,
        target={CONF_ENTITY_ID: [entity_id_matching, entity_id_wrong]},
        behavior="any",
    )

    # Matching entity in matching state - condition should be True
    assert condition_any(hass) is True

    # Set matching entity to non-matching state
    hass.states.async_set(
        entity_id_matching,
        non_matching_state,
        {ATTR_DEVICE_CLASS: device_class, ATTR_IS_CLOSED: non_matching_is_closed},
    )
    await hass.async_block_till_done()

    # Wrong device class entity still in matching state, but should be excluded
    assert condition_any(hass) is False
