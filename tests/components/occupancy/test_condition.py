"""Test occupancy conditions."""

from typing import Any

import pytest

from homeassistant.const import ATTR_DEVICE_CLASS, CONF_ENTITY_ID, STATE_OFF, STATE_ON
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
            required_filter_attributes={ATTR_DEVICE_CLASS: "occupancy"},
        ),
        *parametrize_condition_states_any(
            condition="occupancy.is_not_detected",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            required_filter_attributes={ATTR_DEVICE_CLASS: "occupancy"},
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
    await assert_condition_behavior_any(
        hass,
        target_entities=target_binary_sensors,
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
    parametrize_target_entities("binary_sensor"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_all(
            condition="occupancy.is_detected",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            required_filter_attributes={ATTR_DEVICE_CLASS: "occupancy"},
        ),
        *parametrize_condition_states_all(
            condition="occupancy.is_not_detected",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            required_filter_attributes={ATTR_DEVICE_CLASS: "occupancy"},
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
    await assert_condition_behavior_all(
        hass,
        target_entities=target_binary_sensors,
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
        "state_matching",
        "state_non_matching",
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
    state_matching: str,
    state_non_matching: str,
) -> None:
    """Test occupancy condition excludes entities without device_class occupancy."""
    entity_id_occupancy = "binary_sensor.test_occupancy"
    entity_id_motion = "binary_sensor.test_motion"

    # Set matching states on all entities
    hass.states.async_set(
        entity_id_occupancy,
        state_matching,
        {ATTR_DEVICE_CLASS: "occupancy"},
    )
    hass.states.async_set(
        entity_id_motion, state_matching, {ATTR_DEVICE_CLASS: "motion"}
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
        state_non_matching,
        {ATTR_DEVICE_CLASS: "occupancy"},
    )
    await hass.async_block_till_done()

    # Wrong device class entity still in matching state, but should be excluded
    assert condition_any(hass) is False
