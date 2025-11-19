"""Test cover trigger."""

import pytest

from homeassistant.components.cover import ATTR_CURRENT_POSITION, CoverState
from homeassistant.const import ATTR_DEVICE_CLASS, CONF_ENTITY_ID
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


@pytest.fixture
async def target_covers(hass: HomeAssistant) -> None:
    """Create multiple cover entities associated with different targets."""
    return await target_entities(hass, "cover")


def parametrize_opened_trigger_states(
    trigger: str, device_class: str
) -> list[tuple[str, dict, str, list[StateDescription]]]:
    """Parametrize states and expected service call counts.

    Returns a list of tuples with (trigger, trigger_options,
    list of StateDescription).
    """
    extra_attrs = {ATTR_DEVICE_CLASS: device_class}
    return [
        # States without current position attribute
        *(
            (s[0], {"fully_opened": True}, *s[1:])
            for s in parametrize_trigger_states(
                trigger=trigger,
                target_states=[(CoverState.OPEN, {})],
                other_states=[(CoverState.CLOSED, {})],
                extra_attributes=extra_attrs,
                trigger_from_none=False,
            )
        ),
        *(
            (s[0], {"fully_opened": True}, *s[1:])
            for s in parametrize_trigger_states(
                trigger=trigger,
                target_states=[(CoverState.OPENING, {})],
                other_states=[(CoverState.CLOSED, {})],
                extra_attributes=extra_attrs,
                trigger_from_none=False,
            )
        ),
        *(
            (s[0], {}, *s[1:])
            for s in parametrize_trigger_states(
                trigger=trigger,
                target_states=[(CoverState.OPEN, {})],
                other_states=[(CoverState.CLOSED, {})],
                extra_attributes=extra_attrs,
                trigger_from_none=False,
            )
        ),
        *(
            (s[0], {}, *s[1:])
            for s in parametrize_trigger_states(
                trigger=trigger,
                target_states=[(CoverState.OPENING, {})],
                other_states=[(CoverState.CLOSED, {})],
                extra_attributes=extra_attrs,
                trigger_from_none=False,
            )
        ),
        # States with current position attribute
        *(
            (s[0], {"fully_opened": True}, *s[1:])
            for s in parametrize_trigger_states(
                trigger=trigger,
                target_states=[(CoverState.OPEN, {ATTR_CURRENT_POSITION: 100})],
                other_states=[(CoverState.OPEN, {ATTR_CURRENT_POSITION: 0})],
                extra_attributes=extra_attrs,
                trigger_from_none=False,
            )
        ),
        *(
            (s[0], {"fully_opened": True}, *s[1:])
            for s in parametrize_trigger_states(
                trigger=trigger,
                target_states=[(CoverState.OPENING, {ATTR_CURRENT_POSITION: 100})],
                other_states=[(CoverState.OPENING, {ATTR_CURRENT_POSITION: 0})],
                extra_attributes=extra_attrs,
                trigger_from_none=False,
            )
        ),
        *(
            (s[0], {}, *s[1:])
            for s in parametrize_trigger_states(
                trigger=trigger,
                target_states=[(CoverState.OPEN, {ATTR_CURRENT_POSITION: 1})],
                other_states=[(CoverState.CLOSED, {ATTR_CURRENT_POSITION: 0})],
                extra_attributes=extra_attrs,
                trigger_from_none=False,
            )
        ),
        *(
            (s[0], {}, *s[1:])
            for s in parametrize_trigger_states(
                trigger=trigger,
                target_states=[(CoverState.OPENING, {ATTR_CURRENT_POSITION: 1})],
                other_states=[(CoverState.CLOSED, {ATTR_CURRENT_POSITION: 0})],
                extra_attributes=extra_attrs,
                trigger_from_none=False,
            )
        ),
    ]


@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("cover"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_opened_trigger_states("cover.garage_opened", "garage"),
        # No initial state attribute, doesn't trigger because it's already in target state.
        (
            "cover.garage_opened",
            {"fully_opened": True},
            [
                {
                    "state": CoverState.OPEN,
                    "attributes": {ATTR_DEVICE_CLASS: "garage"},
                    "count": 0,
                },
                {
                    "state": CoverState.OPEN,
                    "attributes": {
                        ATTR_CURRENT_POSITION: 100,
                        ATTR_DEVICE_CLASS: "garage",
                    },
                    "count": 0,
                },
                {
                    "state": CoverState.OPEN,
                    "attributes": {
                        ATTR_CURRENT_POSITION: 0,
                        ATTR_DEVICE_CLASS: "garage",
                    },
                    "count": 0,
                },
                {
                    "state": CoverState.OPEN,
                    "attributes": {
                        ATTR_CURRENT_POSITION: 100,
                        ATTR_DEVICE_CLASS: "garage",
                    },
                    "count": 1,
                },
            ],
        ),
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
        set_or_remove_state(hass, eid, states[0]["state"], states[0]["attributes"])
        await hass.async_block_till_done()

    await arm_trigger(hass, trigger, trigger_options, trigger_target_config)

    for state in states[1:]:
        set_or_remove_state(hass, entity_id, state["state"], state["attributes"])
        await hass.async_block_till_done()
        assert len(service_calls) == state["count"]
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()

        # Check if changing other covers also triggers
        for other_entity_id in other_entity_ids:
            set_or_remove_state(
                hass, other_entity_id, state["state"], state["attributes"]
            )
            await hass.async_block_till_done()
        assert len(service_calls) == (entities_in_target - 1) * state["count"]
        service_calls.clear()


@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("cover"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_opened_trigger_states("cover.garage_opened", "garage"),
        # No initial state attribute, doesn't trigger because it's already in target state.
        (
            "cover.garage_opened",
            {"fully_opened": True},
            [
                {
                    "state": CoverState.OPEN,
                    "attributes": {ATTR_DEVICE_CLASS: "garage"},
                    "count": 0,
                },
                {
                    "state": CoverState.OPEN,
                    "attributes": {
                        ATTR_CURRENT_POSITION: 100,
                        ATTR_DEVICE_CLASS: "garage",
                    },
                    "count": 0,
                },
                {
                    "state": CoverState.OPEN,
                    "attributes": {
                        ATTR_CURRENT_POSITION: 0,
                        ATTR_DEVICE_CLASS: "garage",
                    },
                    "count": 0,
                },
                {
                    "state": CoverState.OPEN,
                    "attributes": {
                        ATTR_CURRENT_POSITION: 100,
                        ATTR_DEVICE_CLASS: "garage",
                    },
                    "count": 1,
                },
            ],
        ),
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
        set_or_remove_state(hass, eid, states[0]["state"], states[0]["attributes"])
        await hass.async_block_till_done()

    await arm_trigger(
        hass,
        trigger,
        {"behavior": "first"} | trigger_options,
        trigger_target_config,
    )

    for state in states[1:]:
        set_or_remove_state(hass, entity_id, state["state"], state["attributes"])
        await hass.async_block_till_done()
        assert len(service_calls) == state["count"]
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()

        # Triggering other covers should not cause the trigger to fire again
        for other_entity_id in other_entity_ids:
            set_or_remove_state(
                hass, other_entity_id, state["state"], state["attributes"]
            )
            await hass.async_block_till_done()
        assert len(service_calls) == 0


@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("cover"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_opened_trigger_states("cover.garage_opened", "garage"),
        # No initial state attribute, doesn't trigger because it's already in target state.
        (
            "cover.garage_opened",
            {"fully_opened": True},
            [
                {
                    "state": CoverState.OPEN,
                    "attributes": {ATTR_DEVICE_CLASS: "garage"},
                    "count": 0,
                },
                {
                    "state": CoverState.OPEN,
                    "attributes": {
                        ATTR_CURRENT_POSITION: 100,
                        ATTR_DEVICE_CLASS: "garage",
                    },
                    "count": 0,
                },
                {
                    "state": CoverState.OPEN,
                    "attributes": {
                        ATTR_CURRENT_POSITION: 0,
                        ATTR_DEVICE_CLASS: "garage",
                    },
                    "count": 0,
                },
                {
                    "state": CoverState.OPEN,
                    "attributes": {
                        ATTR_CURRENT_POSITION: 100,
                        ATTR_DEVICE_CLASS: "garage",
                    },
                    "count": 1,
                },
            ],
        ),
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
        set_or_remove_state(hass, eid, states[0]["state"], states[0]["attributes"])
        await hass.async_block_till_done()

    await arm_trigger(
        hass, trigger, {"behavior": "last"} | trigger_options, trigger_target_config
    )

    for state in states[1:]:
        for other_entity_id in other_entity_ids:
            set_or_remove_state(
                hass, other_entity_id, state["state"], state["attributes"]
            )
            await hass.async_block_till_done()
        assert len(service_calls) == 0

        set_or_remove_state(hass, entity_id, state["state"], state["attributes"])
        await hass.async_block_till_done()
        assert len(service_calls) == state["count"]
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()
