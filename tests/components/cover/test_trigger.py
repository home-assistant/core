"""Test cover triggers."""

from typing import Any

import pytest

from homeassistant.components.cover import ATTR_IS_CLOSED, CoverState
from homeassistant.const import ATTR_DEVICE_CLASS, CONF_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall

from tests.components import (
    TriggerStateDescription,
    arm_trigger,
    assert_trigger_gated_by_labs_flag,
    parametrize_target_entities,
    parametrize_trigger_states,
    set_or_remove_state,
    target_entities,
)

DEVICE_CLASS_TRIGGERS = [
    ("awning", "cover.awning_opened", "cover.awning_closed"),
    ("blind", "cover.blind_opened", "cover.blind_closed"),
    ("curtain", "cover.curtain_opened", "cover.curtain_closed"),
    ("shade", "cover.shade_opened", "cover.shade_closed"),
    ("shutter", "cover.shutter_opened", "cover.shutter_closed"),
]


@pytest.fixture
async def target_covers(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple cover entities associated with different targets."""
    return await target_entities(hass, "cover")


@pytest.mark.parametrize(
    "trigger_key",
    [
        trigger
        for _, opened, closed in DEVICE_CLASS_TRIGGERS
        for trigger in (opened, closed)
    ],
)
async def test_cover_triggers_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, trigger_key: str
) -> None:
    """Test the cover triggers are gated by the labs flag."""
    await assert_trigger_gated_by_labs_flag(hass, caplog, trigger_key)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("cover"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        param
        for device_class, opened_key, closed_key in DEVICE_CLASS_TRIGGERS
        for param in (
            *parametrize_trigger_states(
                trigger=opened_key,
                target_states=[
                    (CoverState.OPEN, {ATTR_IS_CLOSED: False}),
                    (CoverState.OPENING, {ATTR_IS_CLOSED: False}),
                ],
                other_states=[
                    (CoverState.CLOSED, {ATTR_IS_CLOSED: True}),
                    (CoverState.CLOSING, {ATTR_IS_CLOSED: True}),
                ],
                extra_invalid_states=[
                    (CoverState.OPEN, {ATTR_IS_CLOSED: None}),
                    (CoverState.OPEN, {}),
                ],
                additional_attributes={ATTR_DEVICE_CLASS: device_class},
                trigger_from_none=False,
            ),
            *parametrize_trigger_states(
                trigger=closed_key,
                target_states=[
                    (CoverState.CLOSED, {ATTR_IS_CLOSED: True}),
                    (CoverState.CLOSING, {ATTR_IS_CLOSED: True}),
                ],
                other_states=[
                    (CoverState.OPEN, {ATTR_IS_CLOSED: False}),
                    (CoverState.OPENING, {ATTR_IS_CLOSED: False}),
                    (CoverState.CLOSING, {ATTR_IS_CLOSED: False}),
                ],
                extra_invalid_states=[
                    (CoverState.OPEN, {ATTR_IS_CLOSED: None}),
                    (CoverState.OPEN, {}),
                ],
                additional_attributes={ATTR_DEVICE_CLASS: device_class},
                trigger_from_none=False,
            ),
        )
    ],
)
async def test_cover_trigger_behavior_any(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_covers: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test cover trigger fires for cover entities with matching device_class."""
    other_entity_ids = set(target_covers["included"]) - {entity_id}
    excluded_entity_ids = set(target_covers["excluded"]) - {entity_id}

    for eid in target_covers["included"]:
        set_or_remove_state(hass, eid, states[0]["included"])
        await hass.async_block_till_done()
    for eid in excluded_entity_ids:
        set_or_remove_state(hass, eid, states[0]["excluded"])
        await hass.async_block_till_done()

    await arm_trigger(hass, trigger, {}, trigger_target_config)

    for state in states[1:]:
        excluded_state = state["excluded"]
        included_state = state["included"]
        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert len(service_calls) == state["count"]
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()

        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        for excluded_entity_id in excluded_entity_ids:
            set_or_remove_state(hass, excluded_entity_id, excluded_state)
            await hass.async_block_till_done()
        assert len(service_calls) == (entities_in_target - 1) * state["count"]
        service_calls.clear()


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("cover"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        param
        for device_class, opened_key, closed_key in DEVICE_CLASS_TRIGGERS
        for param in (
            *parametrize_trigger_states(
                trigger=opened_key,
                target_states=[
                    (CoverState.OPEN, {ATTR_IS_CLOSED: False}),
                    (CoverState.OPENING, {ATTR_IS_CLOSED: False}),
                ],
                other_states=[
                    (CoverState.CLOSED, {ATTR_IS_CLOSED: True}),
                    (CoverState.CLOSING, {ATTR_IS_CLOSED: True}),
                ],
                extra_invalid_states=[
                    (CoverState.OPEN, {ATTR_IS_CLOSED: None}),
                    (CoverState.OPEN, {}),
                ],
                additional_attributes={ATTR_DEVICE_CLASS: device_class},
                trigger_from_none=False,
            ),
            *parametrize_trigger_states(
                trigger=closed_key,
                target_states=[
                    (CoverState.CLOSED, {ATTR_IS_CLOSED: True}),
                    (CoverState.CLOSING, {ATTR_IS_CLOSED: True}),
                ],
                other_states=[
                    (CoverState.OPEN, {ATTR_IS_CLOSED: False}),
                    (CoverState.OPENING, {ATTR_IS_CLOSED: False}),
                    (CoverState.CLOSING, {ATTR_IS_CLOSED: False}),
                ],
                extra_invalid_states=[
                    (CoverState.OPEN, {ATTR_IS_CLOSED: None}),
                    (CoverState.OPEN, {}),
                ],
                additional_attributes={ATTR_DEVICE_CLASS: device_class},
                trigger_from_none=False,
            ),
        )
    ],
)
async def test_cover_trigger_behavior_first(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_covers: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test cover trigger fires on the first cover state change."""
    other_entity_ids = set(target_covers["included"]) - {entity_id}
    excluded_entity_ids = set(target_covers["excluded"]) - {entity_id}

    for eid in target_covers["included"]:
        set_or_remove_state(hass, eid, states[0]["included"])
        await hass.async_block_till_done()
    for eid in excluded_entity_ids:
        set_or_remove_state(hass, eid, states[0]["excluded"])
        await hass.async_block_till_done()

    await arm_trigger(hass, trigger, {"behavior": "first"}, trigger_target_config)

    for state in states[1:]:
        excluded_state = state["excluded"]
        included_state = state["included"]
        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert len(service_calls) == state["count"]
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()

        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, excluded_state)
            await hass.async_block_till_done()
        for excluded_entity_id in excluded_entity_ids:
            set_or_remove_state(hass, excluded_entity_id, excluded_state)
            await hass.async_block_till_done()
        assert len(service_calls) == 0


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("cover"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        param
        for device_class, opened_key, closed_key in DEVICE_CLASS_TRIGGERS
        for param in (
            *parametrize_trigger_states(
                trigger=opened_key,
                target_states=[
                    (CoverState.OPEN, {ATTR_IS_CLOSED: False}),
                    (CoverState.OPENING, {ATTR_IS_CLOSED: False}),
                ],
                other_states=[
                    (CoverState.CLOSED, {ATTR_IS_CLOSED: True}),
                    (CoverState.CLOSING, {ATTR_IS_CLOSED: True}),
                ],
                extra_invalid_states=[
                    (CoverState.OPEN, {ATTR_IS_CLOSED: None}),
                    (CoverState.OPEN, {}),
                ],
                additional_attributes={ATTR_DEVICE_CLASS: device_class},
                trigger_from_none=False,
            ),
            *parametrize_trigger_states(
                trigger=closed_key,
                target_states=[
                    (CoverState.CLOSED, {ATTR_IS_CLOSED: True}),
                    (CoverState.CLOSING, {ATTR_IS_CLOSED: True}),
                ],
                other_states=[
                    (CoverState.OPEN, {ATTR_IS_CLOSED: False}),
                    (CoverState.OPENING, {ATTR_IS_CLOSED: False}),
                    (CoverState.CLOSING, {ATTR_IS_CLOSED: False}),
                ],
                extra_invalid_states=[
                    (CoverState.OPEN, {ATTR_IS_CLOSED: None}),
                    (CoverState.OPEN, {}),
                ],
                additional_attributes={ATTR_DEVICE_CLASS: device_class},
                trigger_from_none=False,
            ),
        )
    ],
)
async def test_cover_trigger_behavior_last(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_covers: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test cover trigger fires when the last cover changes state."""
    other_entity_ids = set(target_covers["included"]) - {entity_id}
    excluded_entity_ids = set(target_covers["excluded"]) - {entity_id}

    for eid in target_covers["included"]:
        set_or_remove_state(hass, eid, states[0]["included"])
        await hass.async_block_till_done()
    for eid in excluded_entity_ids:
        set_or_remove_state(hass, eid, states[0]["excluded"])
        await hass.async_block_till_done()

    await arm_trigger(hass, trigger, {"behavior": "last"}, trigger_target_config)

    for state in states[1:]:
        excluded_state = state["excluded"]
        included_state = state["included"]
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, excluded_state)
            await hass.async_block_till_done()
        assert len(service_calls) == 0

        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert len(service_calls) == state["count"]
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()

        for excluded_entity_id in excluded_entity_ids:
            set_or_remove_state(hass, excluded_entity_id, excluded_state)
            await hass.async_block_till_done()
        assert len(service_calls) == 0


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    (
        "trigger_key",
        "device_class",
        "wrong_device_class",
        "cover_initial",
        "cover_initial_is_closed",
        "cover_target",
        "cover_target_is_closed",
    ),
    [
        (
            opened_key,
            device_class,
            "damper",
            CoverState.CLOSED,
            True,
            CoverState.OPEN,
            False,
        )
        for device_class, opened_key, _ in DEVICE_CLASS_TRIGGERS
    ]
    + [
        (
            closed_key,
            device_class,
            "damper",
            CoverState.OPEN,
            False,
            CoverState.CLOSED,
            True,
        )
        for device_class, _, closed_key in DEVICE_CLASS_TRIGGERS
    ],
)
async def test_cover_trigger_excludes_non_matching_device_class(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    trigger_key: str,
    device_class: str,
    wrong_device_class: str,
    cover_initial: str,
    cover_initial_is_closed: bool,
    cover_target: str,
    cover_target_is_closed: bool,
) -> None:
    """Test cover trigger does not fire for entities without matching device_class."""
    entity_id_matching = "cover.test_matching"
    entity_id_wrong = "cover.test_wrong"

    # Set initial states
    hass.states.async_set(
        entity_id_matching,
        cover_initial,
        {ATTR_DEVICE_CLASS: device_class, ATTR_IS_CLOSED: cover_initial_is_closed},
    )
    hass.states.async_set(
        entity_id_wrong,
        cover_initial,
        {
            ATTR_DEVICE_CLASS: wrong_device_class,
            ATTR_IS_CLOSED: cover_initial_is_closed,
        },
    )
    await hass.async_block_till_done()

    await arm_trigger(
        hass,
        trigger_key,
        {},
        {
            CONF_ENTITY_ID: [
                entity_id_matching,
                entity_id_wrong,
            ]
        },
    )

    # Matching device class changes - should trigger
    hass.states.async_set(
        entity_id_matching,
        cover_target,
        {ATTR_DEVICE_CLASS: device_class, ATTR_IS_CLOSED: cover_target_is_closed},
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_id_matching
    service_calls.clear()

    # Wrong device class changes - should NOT trigger
    hass.states.async_set(
        entity_id_wrong,
        cover_target,
        {
            ATTR_DEVICE_CLASS: wrong_device_class,
            ATTR_IS_CLOSED: cover_target_is_closed,
        },
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 0
