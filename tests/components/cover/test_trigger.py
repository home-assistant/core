"""Test cover trigger."""

import pytest

from homeassistant.components import automation
from homeassistant.components.cover import ATTR_CURRENT_POSITION, CoverState
from homeassistant.const import (
    CONF_ENTITY_ID,
    CONF_OPTIONS,
    CONF_PLATFORM,
    CONF_TARGET,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component

from tests.components import parametrize_target_entities, target_entities


@pytest.fixture(autouse=True, name="stub_blueprint_populate")
def stub_blueprint_populate_autouse(stub_blueprint_populate: None) -> None:
    """Stub copying the blueprints to the config folder."""


@pytest.fixture
async def target_covers(hass: HomeAssistant) -> None:
    """Create multiple cover entities associated with different targets."""
    return await target_entities(hass, "cover")


def set_or_remove_state(
    hass: HomeAssistant,
    entity_id: str,
    state: str | None,
    attributes: dict | None = None,
) -> None:
    """Set or clear the state of an entity."""
    if state is None:
        hass.states.async_remove(entity_id)
    else:
        hass.states.async_set(entity_id, state, attributes, force_update=True)


async def setup_automation(
    hass: HomeAssistant, trigger: str, trigger_options: dict, trigger_target: dict
) -> None:
    """Set up automation component with given config."""
    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    CONF_PLATFORM: trigger,
                    CONF_OPTIONS: {**trigger_options},
                    CONF_TARGET: {**trigger_target},
                },
                "action": {
                    "service": "test.automation",
                    "data_template": {CONF_ENTITY_ID: "{{ trigger.entity_id }}"},
                },
            }
        },
    )


def parametrize_opened_closed_trigger_states(
    trigger: str,
    trigger_options: dict,
    device_class: str,
    target_state: tuple[str, dict],
    other_state: tuple[str, dict],
) -> list[
    tuple[str, tuple[str | None, dict], list[tuple[tuple[str | None, dict], int]]]
]:
    """Parametrize states and expected service call counts.

    Returns a list of tuples with (trigger, trigger_options, device_class,
    initial_state, list of states), where states is a list of tuples
    (state to set, expected service call count).
    """
    return [
        ## TODO: Check what happens if attribute is missing
        # Initial state None
        (
            trigger,
            trigger_options,
            device_class,
            (None, {}),
            [
                (target_state, 0),
                (other_state, 0),
                # This doesn't trigger because the device class is not set
                # when the trigger is created. We need to teach TargetStateChangeTracker
                # about device classes.
                (target_state, 0),
            ],
        ),
        # Initial state different from target state
        (
            trigger,
            trigger_options,
            device_class,
            other_state,
            [
                (target_state, 1),
                (other_state, 0),
                (target_state, 1),
            ],
        ),
        # Initial state same as target state
        (
            trigger,
            trigger_options,
            device_class,
            target_state,
            [
                (target_state, 0),
                (other_state, 0),
                (target_state, 1),
            ],
        ),
        # Initial state unavailable / unknown
        (
            trigger,
            trigger_options,
            device_class,
            (STATE_UNAVAILABLE, {}),
            [
                (target_state, 0),
                (other_state, 0),
                (target_state, 1),
            ],
        ),
        (
            trigger,
            trigger_options,
            device_class,
            (STATE_UNKNOWN, {}),
            [
                (target_state, 0),
                (other_state, 0),
                (target_state, 1),
            ],
        ),
    ]


def parametrize_opened_trigger_states(
    trigger: str, device_class: str
) -> list[
    tuple[str, tuple[str | None, dict], list[tuple[tuple[str | None, dict], int]]]
]:
    """Parametrize states and expected service call counts.

    Returns a list of tuples with (trigger, trigger_options, device_class,
    initial_state, list of states), where states is a list of tuples
    (state to set, expected service call count).
    """
    return [
        # States without current position attribute
        *parametrize_opened_closed_trigger_states(
            trigger,
            {"fully_opened": True},
            device_class,
            (CoverState.OPEN, {}),
            (CoverState.CLOSED, {}),
        ),
        *parametrize_opened_closed_trigger_states(
            trigger,
            {"fully_opened": True},
            device_class,
            (CoverState.OPENING, {}),
            (CoverState.CLOSED, {}),
        ),
        *parametrize_opened_closed_trigger_states(
            trigger,
            {},
            device_class,
            (CoverState.OPEN, {}),
            (CoverState.CLOSED, {}),
        ),
        *parametrize_opened_closed_trigger_states(
            trigger,
            {},
            device_class,
            (CoverState.OPENING, {}),
            (CoverState.CLOSED, {}),
        ),
        # States with current position attribute
        *parametrize_opened_closed_trigger_states(
            trigger,
            {"fully_opened": True},
            device_class,
            (CoverState.OPEN, {ATTR_CURRENT_POSITION: 100}),
            (CoverState.OPEN, {ATTR_CURRENT_POSITION: 0}),
        ),
        *parametrize_opened_closed_trigger_states(
            trigger,
            {"fully_opened": True},
            device_class,
            (CoverState.OPENING, {ATTR_CURRENT_POSITION: 100}),
            (CoverState.OPENING, {ATTR_CURRENT_POSITION: 0}),
        ),
        *parametrize_opened_closed_trigger_states(
            trigger,
            {},
            device_class,
            (CoverState.OPEN, {ATTR_CURRENT_POSITION: 1}),
            (CoverState.CLOSED, {ATTR_CURRENT_POSITION: 0}),
        ),
        *parametrize_opened_closed_trigger_states(
            trigger,
            {},
            device_class,
            (CoverState.OPENING, {ATTR_CURRENT_POSITION: 1}),
            (CoverState.CLOSED, {ATTR_CURRENT_POSITION: 0}),
        ),
    ]


@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("cover"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "device_class", "initial_state", "states"),
    [
        *parametrize_opened_trigger_states("cover.garage_opened", "garage"),
        # No initial state attribute.
        (
            "cover.garage_opened",
            {"fully_opened": True},
            "garage",
            (CoverState.OPEN, {}),
            [
                ((CoverState.OPEN, {ATTR_CURRENT_POSITION: 100}), 1),
                ((CoverState.OPEN, {ATTR_CURRENT_POSITION: 0}), 0),
                ((CoverState.OPEN, {ATTR_CURRENT_POSITION: 100}), 1),
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
    device_class: str,
    initial_state: tuple[str | None, dict],
    states: list[tuple[tuple[str, dict], int]],
) -> None:
    """Test that the cover state trigger fires when any cover state changes to a specific state."""
    await async_setup_component(hass, "cover", {})

    other_entity_ids = set(target_covers) - {entity_id}

    # Set all covers, including the tested cover, to the initial state
    for eid in target_covers:
        set_or_remove_state(
            hass, eid, initial_state[0], initial_state[1] | {"device_class": "garage"}
        )
        await hass.async_block_till_done()

    await setup_automation(hass, trigger, trigger_options, trigger_target_config)

    for state, expected_calls in states:
        set_or_remove_state(
            hass, entity_id, state[0], state[1] | {"device_class": "garage"}
        )
        await hass.async_block_till_done()
        assert len(service_calls) == expected_calls
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()

        # Check if changing other covers also triggers
        for other_entity_id in other_entity_ids:
            set_or_remove_state(
                hass, other_entity_id, state[0], state[1] | {"device_class": "garage"}
            )
            await hass.async_block_till_done()
        assert len(service_calls) == (entities_in_target - 1) * expected_calls
        service_calls.clear()


@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("cover"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "device_class", "initial_state", "states"),
    [
        *parametrize_opened_trigger_states("cover.garage_opened", "garage"),
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
    device_class: str,
    initial_state: tuple[str | None, dict],
    states: list[tuple[tuple[str, dict], int]],
) -> None:
    """Test that the cover state trigger fires when the first cover state changes to a specific state."""
    await async_setup_component(hass, "cover", {})

    other_entity_ids = set(target_covers) - {entity_id}

    # Set all covers, including the tested cover, to the initial state
    for eid in target_covers:
        set_or_remove_state(
            hass, eid, initial_state[0], initial_state[1] | {"device_class": "garage"}
        )
        await hass.async_block_till_done()

    await setup_automation(
        hass,
        trigger,
        {"behavior": "first"} | trigger_options,
        trigger_target_config,
    )

    for state, expected_calls in states:
        set_or_remove_state(
            hass, entity_id, state[0], state[1] | {"device_class": "garage"}
        )
        await hass.async_block_till_done()
        assert len(service_calls) == expected_calls
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()

        # Triggering other covers should not cause the trigger to fire again
        for other_entity_id in other_entity_ids:
            set_or_remove_state(
                hass, other_entity_id, state[0], state[1] | {"device_class": "garage"}
            )
            await hass.async_block_till_done()
        assert len(service_calls) == 0


@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("cover"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "device_class", "initial_state", "states"),
    [
        *parametrize_opened_trigger_states("cover.garage_opened", "garage"),
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
    device_class: str,
    initial_state: tuple[str | None, dict],
    states: list[tuple[tuple[str, dict], int]],
) -> None:
    """Test that the cover state trigger fires when the last cover state changes to a specific state."""
    await async_setup_component(hass, "cover", {})

    other_entity_ids = set(target_covers) - {entity_id}

    # Set all covers, including the tested cover, to the initial state
    for eid in target_covers:
        set_or_remove_state(
            hass, eid, initial_state[0], initial_state[1] | {"device_class": "garage"}
        )
        await hass.async_block_till_done()

    await setup_automation(
        hass, trigger, {"behavior": "last"} | trigger_options, trigger_target_config
    )

    for state, expected_calls in states:
        for other_entity_id in other_entity_ids:
            set_or_remove_state(
                hass, other_entity_id, state[0], state[1] | {"device_class": "garage"}
            )
            await hass.async_block_till_done()
        assert len(service_calls) == 0

        set_or_remove_state(
            hass, entity_id, state[0], state[1] | {"device_class": "garage"}
        )
        await hass.async_block_till_done()
        assert len(service_calls) == expected_calls
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()
