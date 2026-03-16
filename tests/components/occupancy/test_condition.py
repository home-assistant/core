"""Test occupancy conditions."""

from typing import Any

import pytest

from homeassistant.const import ATTR_DEVICE_CLASS, CONF_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from tests.components import (
    ConditionStateDescription,
    assert_condition_gated_by_labs_flag,
    create_target_condition,
    parametrize_condition_states_all,
    parametrize_condition_states_any,
    parametrize_target_entities,
    set_or_remove_state,
    target_entities,
)


@pytest.fixture
async def target_binary_sensors(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple binary sensor entities associated with different targets."""
    return await target_entities(hass, "binary_sensor")


@pytest.mark.parametrize(
    "condition",
    [
        "occupancy.is_detected",
        "occupancy.is_not_detected",
    ],
)
async def test_occupancy_conditions_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, condition: str
) -> None:
    """Test the occupancy conditions are gated by the labs flag."""
    await assert_condition_gated_by_labs_flag(hass, caplog, condition)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("binary_sensor"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_any(
            condition="occupancy.is_detected",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            additional_attributes={ATTR_DEVICE_CLASS: "occupancy"},
        ),
        *parametrize_condition_states_any(
            condition="occupancy.is_not_detected",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            additional_attributes={ATTR_DEVICE_CLASS: "occupancy"},
        ),
    ],
)
async def test_occupancy_binary_sensor_condition_behavior_any(
    hass: HomeAssistant,
    target_binary_sensors: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test occupancy condition for binary_sensor with 'any' behavior."""
    other_entity_ids = set(target_binary_sensors["included"]) - {entity_id}
    excluded_entity_ids = set(target_binary_sensors["excluded"]) - {entity_id}

    for eid in target_binary_sensors["included"]:
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
    parametrize_target_entities("binary_sensor"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_all(
            condition="occupancy.is_detected",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            additional_attributes={ATTR_DEVICE_CLASS: "occupancy"},
        ),
        *parametrize_condition_states_all(
            condition="occupancy.is_not_detected",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            additional_attributes={ATTR_DEVICE_CLASS: "occupancy"},
        ),
    ],
)
async def test_occupancy_binary_sensor_condition_behavior_all(
    hass: HomeAssistant,
    target_binary_sensors: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test occupancy condition for binary_sensor with 'all' behavior."""
    other_entity_ids = set(target_binary_sensors["included"]) - {entity_id}
    excluded_entity_ids = set(target_binary_sensors["excluded"]) - {entity_id}

    for eid in target_binary_sensors["included"]:
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


# --- Device class exclusion test ---


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    (
        "condition_key",
        "binary_sensor_matching",
        "binary_sensor_non_matching",
    ),
    [
        (
            "occupancy.is_detected",
            STATE_ON,
            STATE_OFF,
        ),
        (
            "occupancy.is_not_detected",
            STATE_OFF,
            STATE_ON,
        ),
    ],
)
async def test_occupancy_condition_excludes_non_occupancy_device_class(
    hass: HomeAssistant,
    condition_key: str,
    binary_sensor_matching: str,
    binary_sensor_non_matching: str,
) -> None:
    """Test occupancy condition excludes entities without device_class occupancy."""
    entity_id_occupancy = "binary_sensor.test_occupancy"
    entity_id_motion = "binary_sensor.test_motion"

    # Set matching states on all entities
    hass.states.async_set(
        entity_id_occupancy,
        binary_sensor_matching,
        {ATTR_DEVICE_CLASS: "occupancy"},
    )
    hass.states.async_set(
        entity_id_motion, binary_sensor_matching, {ATTR_DEVICE_CLASS: "motion"}
    )
    await hass.async_block_till_done()

    condition_any = await create_target_condition(
        hass,
        condition=condition_key,
        target={CONF_ENTITY_ID: [entity_id_occupancy, entity_id_motion]},
        behavior="any",
    )

    # Matching entity in matching state - condition should be True
    assert condition_any(hass) is True

    # Set matching entity to non-matching state
    hass.states.async_set(
        entity_id_occupancy,
        binary_sensor_non_matching,
        {ATTR_DEVICE_CLASS: "occupancy"},
    )
    await hass.async_block_till_done()

    # Wrong device class entity still in matching state, but should be excluded
    assert condition_any(hass) is False
