"""Test climate trigger."""

import pytest

from homeassistant.components.climate.const import (
    ATTR_HVAC_ACTION,
    HVACAction,
    HVACMode,
)
from homeassistant.const import CONF_ENTITY_ID
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
async def target_climates(hass: HomeAssistant) -> None:
    """Create multiple climate entities associated with different targets."""
    return await target_entities(hass, "climate")


@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("climate"),
)
@pytest.mark.parametrize(
    ("trigger", "states"),
    [
        *parametrize_trigger_states(
            trigger="climate.turned_off",
            target_states=[HVACMode.OFF],
            other_states=[HVACMode.HEAT],
        ),
        *parametrize_trigger_states(
            trigger="climate.turned_on",
            target_states=[
                HVACAction.COOLING,
                HVACAction.DEFROSTING,
                HVACAction.DRYING,
                HVACAction.FAN,
                HVACAction.HEATING,
                HVACAction.IDLE,
                HVACAction.PREHEATING,
            ],
            other_states=[
                HVACAction.OFF,
            ],
        ),
    ],
)
async def test_climate_state_trigger_behavior_any(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_climates: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    states: list[StateDescription],
) -> None:
    """Test that the climate state trigger fires when any climate state changes to a specific state."""
    await async_setup_component(hass, "climate", {})

    other_entity_ids = set(target_climates) - {entity_id}

    # Set all climates, including the tested climate, to the initial state
    for eid in target_climates:
        set_or_remove_state(hass, eid, states[0])
        await hass.async_block_till_done()

    await arm_trigger(hass, trigger, {}, trigger_target_config)

    for state in states[1:]:
        set_or_remove_state(hass, entity_id, state)
        await hass.async_block_till_done()
        assert len(service_calls) == state["count"]
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()

        # Check if changing other climates also triggers
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, state)
            await hass.async_block_till_done()
        assert len(service_calls) == (entities_in_target - 1) * state["count"]
        service_calls.clear()


@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("climate"),
)
@pytest.mark.parametrize(
    ("trigger", "states"),
    [
        *parametrize_trigger_states(
            trigger="climate.started_heating",
            target_states=[(HVACMode.OFF, {ATTR_HVAC_ACTION: HVACAction.HEATING})],
            other_states=[(HVACMode.OFF, {ATTR_HVAC_ACTION: HVACAction.IDLE})],
        )
    ],
)
async def test_climate_state_attribute_trigger_behavior_any(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_climates: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    states: list[StateDescription],
) -> None:
    """Test that the climate state trigger fires when any climate state changes to a specific state."""
    await async_setup_component(hass, "climate", {})

    other_entity_ids = set(target_climates) - {entity_id}

    # Set all climates, including the tested climate, to the initial state
    for eid in target_climates:
        set_or_remove_state(hass, eid, states[0])
        await hass.async_block_till_done()

    await arm_trigger(hass, trigger, {}, trigger_target_config)

    for state in states[1:]:
        set_or_remove_state(hass, entity_id, state)
        await hass.async_block_till_done()
        assert len(service_calls) == state["count"]
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()

        # Check if changing other climates also triggers
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, state)
            await hass.async_block_till_done()
        assert len(service_calls) == (entities_in_target - 1) * state["count"]
        service_calls.clear()


@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("climate"),
)
@pytest.mark.parametrize(
    ("trigger", "states"),
    [
        *parametrize_trigger_states(
            trigger="climate.turned_off",
            target_states=[HVACMode.OFF],
            other_states=[HVACMode.HEAT],
        ),
        *parametrize_trigger_states(
            trigger="climate.turned_on",
            target_states=[
                HVACAction.COOLING,
                HVACAction.DEFROSTING,
                HVACAction.DRYING,
                HVACAction.FAN,
                HVACAction.HEATING,
                HVACAction.IDLE,
                HVACAction.PREHEATING,
            ],
            other_states=[
                HVACAction.OFF,
            ],
        ),
    ],
)
async def test_climate_state_trigger_behavior_first(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_climates: list[str],
    trigger_target_config: dict,
    entities_in_target: int,
    entity_id: str,
    trigger: str,
    states: list[StateDescription],
) -> None:
    """Test that the climate state trigger fires when the first climate changes to a specific state."""
    await async_setup_component(hass, "climate", {})

    other_entity_ids = set(target_climates) - {entity_id}

    # Set all climates, including the tested climate, to the initial state
    for eid in target_climates:
        set_or_remove_state(hass, eid, states[0])
        await hass.async_block_till_done()

    await arm_trigger(hass, trigger, {"behavior": "first"}, trigger_target_config)

    for state in states[1:]:
        set_or_remove_state(hass, entity_id, state)
        await hass.async_block_till_done()
        assert len(service_calls) == state["count"]
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()

        # Triggering other climates should not cause the trigger to fire again
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, state)
            await hass.async_block_till_done()
        assert len(service_calls) == 0


@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("climate"),
)
@pytest.mark.parametrize(
    ("trigger", "states"),
    [
        *parametrize_trigger_states(
            trigger="climate.started_heating",
            target_states=[(HVACMode.OFF, {ATTR_HVAC_ACTION: HVACAction.HEATING})],
            other_states=[(HVACMode.OFF, {ATTR_HVAC_ACTION: HVACAction.IDLE})],
        )
    ],
)
async def test_climate_state_attribute_trigger_behavior_first(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_climates: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    states: list[tuple[tuple[str, dict], int]],
) -> None:
    """Test that the climate state trigger fires when any climate state changes to a specific state."""
    await async_setup_component(hass, "climate", {})

    other_entity_ids = set(target_climates) - {entity_id}

    # Set all climates, including the tested climate, to the initial state
    for eid in target_climates:
        set_or_remove_state(hass, eid, states[0])
        await hass.async_block_till_done()

    await arm_trigger(hass, trigger, {"behavior": "first"}, trigger_target_config)

    for state in states[1:]:
        set_or_remove_state(hass, entity_id, state)
        await hass.async_block_till_done()
        assert len(service_calls) == state["count"]
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()

        # Triggering other climates should not cause the trigger to fire again
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, state)
            await hass.async_block_till_done()
        assert len(service_calls) == 0


@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("climate"),
)
@pytest.mark.parametrize(
    ("trigger", "states"),
    [
        *parametrize_trigger_states(
            trigger="climate.turned_off",
            target_states=[HVACMode.OFF],
            other_states=[HVACMode.HEAT],
        ),
        *parametrize_trigger_states(
            trigger="climate.turned_on",
            target_states=[
                HVACAction.COOLING,
                HVACAction.DEFROSTING,
                HVACAction.DRYING,
                HVACAction.FAN,
                HVACAction.HEATING,
                HVACAction.IDLE,
                HVACAction.PREHEATING,
            ],
            other_states=[
                HVACAction.OFF,
            ],
        ),
    ],
)
async def test_climate_state_trigger_behavior_last(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_climates: list[str],
    trigger_target_config: dict,
    entities_in_target: int,
    entity_id: str,
    trigger: str,
    states: list[StateDescription],
) -> None:
    """Test that the climate state trigger fires when the last climate changes to a specific state."""
    await async_setup_component(hass, "climate", {})

    other_entity_ids = set(target_climates) - {entity_id}

    # Set all climates, including the tested climate, to the initial state
    for eid in target_climates:
        set_or_remove_state(hass, eid, states[0])
        await hass.async_block_till_done()

    await arm_trigger(hass, trigger, {"behavior": "last"}, trigger_target_config)

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


@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("climate"),
)
@pytest.mark.parametrize(
    ("trigger", "states"),
    [
        *parametrize_trigger_states(
            trigger="climate.started_heating",
            target_states=[(HVACMode.OFF, {ATTR_HVAC_ACTION: HVACAction.HEATING})],
            other_states=[(HVACMode.OFF, {ATTR_HVAC_ACTION: HVACAction.IDLE})],
        )
    ],
)
async def test_climate_state_attribute_trigger_behavior_last(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_climates: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    states: list[tuple[tuple[str, dict], int]],
) -> None:
    """Test that the climate state trigger fires when any climate state changes to a specific state."""
    await async_setup_component(hass, "climate", {})

    other_entity_ids = set(target_climates) - {entity_id}

    # Set all climates, including the tested climate, to the initial state
    for eid in target_climates:
        set_or_remove_state(hass, eid, states[0])
        await hass.async_block_till_done()

    await arm_trigger(hass, trigger, {"behavior": "last"}, trigger_target_config)

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
