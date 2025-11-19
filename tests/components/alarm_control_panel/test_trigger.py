"""Test alarm control panel triggers."""

from collections.abc import Iterable

import pytest

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component

from tests.components import (
    arm_trigger,
    parametrize_target_entities,
    parametrize_trigger_states,
    target_entities,
)

ACP_STATES = {s.value for s in AlarmControlPanelState}


@pytest.fixture(autouse=True, name="stub_blueprint_populate")
def stub_blueprint_populate_autouse(stub_blueprint_populate: None) -> None:
    """Stub copying the blueprints to the config folder."""


@pytest.fixture
async def target_alarm_control_panels(hass: HomeAssistant) -> None:
    """Create multiple alarm control panel entities associated with different targets."""
    return await target_entities(hass, "alarm_control_panel")


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


def parametrize_acp_trigger_states(
    trigger: str,
    target_states: Iterable[str],
    other_states: Iterable[str],
    supported_features: int,
) -> list[tuple[str, int, list[tuple[str | None, int]]]]:
    """Parametrize states and expected service call counts.

    Returns a list of tuples with (trigger, supported_features, list of states),
    where states is a list of tuples (state to set, expected service call count).
    """
    return [
        (s[0], supported_features, *s[1:])
        for s in parametrize_trigger_states(
            trigger,
            target_states,
            other_states,
            trigger_from_none=supported_features == 0,
        )
    ]


@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("alarm_control_panel"),
)
@pytest.mark.parametrize(
    ("trigger", "supported_features", "states"),
    [
        *parametrize_acp_trigger_states(
            "alarm_control_panel.armed_away",
            (AlarmControlPanelState.ARMED_AWAY,),
            ACP_STATES - {AlarmControlPanelState.ARMED_AWAY},
            AlarmControlPanelEntityFeature.ARM_AWAY,
        ),
        *parametrize_acp_trigger_states(
            "alarm_control_panel.armed_home",
            (AlarmControlPanelState.ARMED_HOME,),
            ACP_STATES - {AlarmControlPanelState.ARMED_HOME},
            AlarmControlPanelEntityFeature.ARM_HOME,
        ),
        *parametrize_acp_trigger_states(
            "alarm_control_panel.armed_night",
            (AlarmControlPanelState.ARMED_NIGHT,),
            ACP_STATES - {AlarmControlPanelState.ARMED_NIGHT},
            AlarmControlPanelEntityFeature.ARM_NIGHT,
        ),
        *parametrize_acp_trigger_states(
            "alarm_control_panel.armed_vacation",
            (AlarmControlPanelState.ARMED_VACATION,),
            ACP_STATES - {AlarmControlPanelState.ARMED_VACATION},
            AlarmControlPanelEntityFeature.ARM_VACATION,
        ),
        *parametrize_acp_trigger_states(
            "alarm_control_panel.disarmed",
            (AlarmControlPanelState.DISARMED,),
            ACP_STATES - {AlarmControlPanelState.DISARMED},
            0,
        ),
        *parametrize_acp_trigger_states(
            "alarm_control_panel.triggered",
            (AlarmControlPanelState.TRIGGERED,),
            ACP_STATES - {AlarmControlPanelState.TRIGGERED},
            0,
        ),
    ],
)
async def test_alarm_control_panel_state_trigger_behavior_any(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_alarm_control_panels: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    supported_features: int,
    states: list[tuple[str, int]],
) -> None:
    """Test that the alarm control panel state trigger fires when any alarm control panel state changes to a specific state."""
    await async_setup_component(hass, "alarm_control_panel", {})

    other_entity_ids = set(target_alarm_control_panels) - {entity_id}

    # Set all alarm control panels, including the tested one, to the initial state
    for eid in target_alarm_control_panels:
        set_or_remove_state(
            hass, eid, states[0][0], {"supported_features": supported_features}
        )
        await hass.async_block_till_done()

    await arm_trigger(hass, trigger, {}, trigger_target_config)

    for state, expected_calls in states[1:]:
        set_or_remove_state(
            hass, entity_id, state, {"supported_features": supported_features}
        )
        await hass.async_block_till_done()
        assert len(service_calls) == expected_calls
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()

        # Check if changing other alarm control panels also triggers
        for other_entity_id in other_entity_ids:
            set_or_remove_state(
                hass, other_entity_id, state, {"supported_features": supported_features}
            )
            await hass.async_block_till_done()
        assert len(service_calls) == (entities_in_target - 1) * expected_calls
        service_calls.clear()


@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("alarm_control_panel"),
)
@pytest.mark.parametrize(
    ("trigger", "supported_features", "states"),
    [
        *parametrize_acp_trigger_states(
            "alarm_control_panel.armed_away",
            (AlarmControlPanelState.ARMED_AWAY,),
            ACP_STATES - {AlarmControlPanelState.ARMED_AWAY},
            AlarmControlPanelEntityFeature.ARM_AWAY,
        ),
        *parametrize_acp_trigger_states(
            "alarm_control_panel.armed_home",
            (AlarmControlPanelState.ARMED_HOME,),
            ACP_STATES - {AlarmControlPanelState.ARMED_HOME},
            AlarmControlPanelEntityFeature.ARM_HOME,
        ),
        *parametrize_acp_trigger_states(
            "alarm_control_panel.armed_night",
            (AlarmControlPanelState.ARMED_NIGHT,),
            ACP_STATES - {AlarmControlPanelState.ARMED_NIGHT},
            AlarmControlPanelEntityFeature.ARM_NIGHT,
        ),
        *parametrize_acp_trigger_states(
            "alarm_control_panel.armed_vacation",
            (AlarmControlPanelState.ARMED_VACATION,),
            ACP_STATES - {AlarmControlPanelState.ARMED_VACATION},
            AlarmControlPanelEntityFeature.ARM_VACATION,
        ),
        *parametrize_acp_trigger_states(
            "alarm_control_panel.disarmed",
            (AlarmControlPanelState.DISARMED,),
            ACP_STATES - {AlarmControlPanelState.DISARMED},
            0,
        ),
        *parametrize_acp_trigger_states(
            "alarm_control_panel.triggered",
            (AlarmControlPanelState.TRIGGERED,),
            ACP_STATES - {AlarmControlPanelState.TRIGGERED},
            0,
        ),
    ],
)
async def test_alarm_control_panel_state_trigger_behavior_first(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_alarm_control_panels: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    supported_features: int,
    states: list[tuple[str, int, list[str]]],
) -> None:
    """Test that the alarm control panel state trigger fires when the first alarm control panel changes to a specific state."""
    await async_setup_component(hass, "alarm_control_panel", {})

    other_entity_ids = set(target_alarm_control_panels) - {entity_id}

    # Set all alarm control panels, including the tested one, to the initial state
    for eid in target_alarm_control_panels:
        set_or_remove_state(
            hass, eid, states[0][0], {"supported_features": supported_features}
        )
        await hass.async_block_till_done()

    await arm_trigger(hass, trigger, {"behavior": "first"}, trigger_target_config)

    for state, expected_calls in states[1:]:
        set_or_remove_state(
            hass, entity_id, state, {"supported_features": supported_features}
        )
        await hass.async_block_till_done()
        assert len(service_calls) == expected_calls
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()

        # Triggering other alarm control panels should not cause the trigger to fire again
        for other_entity_id in other_entity_ids:
            set_or_remove_state(
                hass, other_entity_id, state, {"supported_features": supported_features}
            )
            await hass.async_block_till_done()
        assert len(service_calls) == 0


@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("alarm_control_panel"),
)
@pytest.mark.parametrize(
    ("trigger", "supported_features", "states"),
    [
        *parametrize_acp_trigger_states(
            "alarm_control_panel.armed_away",
            (AlarmControlPanelState.ARMED_AWAY,),
            ACP_STATES - {AlarmControlPanelState.ARMED_AWAY},
            AlarmControlPanelEntityFeature.ARM_AWAY,
        ),
        *parametrize_acp_trigger_states(
            "alarm_control_panel.armed_home",
            (AlarmControlPanelState.ARMED_HOME,),
            ACP_STATES - {AlarmControlPanelState.ARMED_HOME},
            AlarmControlPanelEntityFeature.ARM_HOME,
        ),
        *parametrize_acp_trigger_states(
            "alarm_control_panel.armed_night",
            (AlarmControlPanelState.ARMED_NIGHT,),
            ACP_STATES - {AlarmControlPanelState.ARMED_NIGHT},
            AlarmControlPanelEntityFeature.ARM_NIGHT,
        ),
        *parametrize_acp_trigger_states(
            "alarm_control_panel.armed_vacation",
            (AlarmControlPanelState.ARMED_VACATION,),
            ACP_STATES - {AlarmControlPanelState.ARMED_VACATION},
            AlarmControlPanelEntityFeature.ARM_VACATION,
        ),
        *parametrize_acp_trigger_states(
            "alarm_control_panel.disarmed",
            (AlarmControlPanelState.DISARMED,),
            ACP_STATES - {AlarmControlPanelState.DISARMED},
            0,
        ),
        *parametrize_acp_trigger_states(
            "alarm_control_panel.triggered",
            (AlarmControlPanelState.TRIGGERED,),
            ACP_STATES - {AlarmControlPanelState.TRIGGERED},
            0,
        ),
    ],
)
async def test_alarm_control_panel_state_trigger_behavior_last(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_alarm_control_panels: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    supported_features: int,
    states: list[tuple[str, int]],
) -> None:
    """Test that the alarm_control_panel state trigger fires when the last alarm_control_panel changes to a specific state."""
    await async_setup_component(hass, "alarm_control_panel", {})

    other_entity_ids = set(target_alarm_control_panels) - {entity_id}

    # Set all alarm control panels, including the tested one, to the initial state
    for eid in target_alarm_control_panels:
        set_or_remove_state(
            hass, eid, states[0][0], {"supported_features": supported_features}
        )
        await hass.async_block_till_done()

    await arm_trigger(hass, trigger, {"behavior": "last"}, trigger_target_config)

    for state, expected_calls in states[1:]:
        for other_entity_id in other_entity_ids:
            set_or_remove_state(
                hass, other_entity_id, state, {"supported_features": supported_features}
            )
            await hass.async_block_till_done()
        assert len(service_calls) == 0

        set_or_remove_state(
            hass, entity_id, state, {"supported_features": supported_features}
        )
        await hass.async_block_till_done()
        assert len(service_calls) == expected_calls
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()
