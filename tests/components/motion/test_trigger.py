"""Test motion trigger."""

from typing import Any

import pytest

from homeassistant.const import ATTR_DEVICE_CLASS, CONF_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, ServiceCall

from tests.components.common import (
    TriggerStateDescription,
    arm_trigger,
    assert_trigger_behavior_any,
    assert_trigger_behavior_first,
    assert_trigger_behavior_last,
    assert_trigger_gated_by_labs_flag,
    parametrize_target_entities,
    parametrize_trigger_states,
    target_entities,
)


@pytest.fixture
async def target_binary_sensors(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple binary sensor entities associated with different targets."""
    return await target_entities(hass, "binary_sensor")


@pytest.mark.parametrize(
    "trigger_key",
    [
        "motion.detected",
        "motion.cleared",
    ],
)
async def test_motion_triggers_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, trigger_key: str
) -> None:
    """Test the motion triggers are gated by the labs flag."""
    await assert_trigger_gated_by_labs_flag(hass, caplog, trigger_key)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("binary_sensor"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="motion.detected",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            required_filter_attributes={ATTR_DEVICE_CLASS: "motion"},
            trigger_from_none=False,
        ),
        *parametrize_trigger_states(
            trigger="motion.cleared",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            required_filter_attributes={ATTR_DEVICE_CLASS: "motion"},
            trigger_from_none=False,
        ),
    ],
)
async def test_motion_trigger_binary_sensor_behavior_any(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_binary_sensors: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test motion trigger fires for binary_sensor entities with device_class motion."""
    await assert_trigger_behavior_any(
        hass,
        service_calls=service_calls,
        target_entities=target_binary_sensors,
        trigger_target_config=trigger_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        trigger=trigger,
        trigger_options=trigger_options,
        states=states,
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("binary_sensor"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="motion.detected",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            required_filter_attributes={ATTR_DEVICE_CLASS: "motion"},
            trigger_from_none=False,
        ),
        *parametrize_trigger_states(
            trigger="motion.cleared",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            required_filter_attributes={ATTR_DEVICE_CLASS: "motion"},
            trigger_from_none=False,
        ),
    ],
)
async def test_motion_trigger_binary_sensor_behavior_first(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_binary_sensors: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test motion trigger fires on the first binary_sensor state change."""
    await assert_trigger_behavior_first(
        hass,
        service_calls=service_calls,
        target_entities=target_binary_sensors,
        trigger_target_config=trigger_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        trigger=trigger,
        trigger_options=trigger_options,
        states=states,
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("binary_sensor"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="motion.detected",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            required_filter_attributes={ATTR_DEVICE_CLASS: "motion"},
            trigger_from_none=False,
        ),
        *parametrize_trigger_states(
            trigger="motion.cleared",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            required_filter_attributes={ATTR_DEVICE_CLASS: "motion"},
            trigger_from_none=False,
        ),
    ],
)
async def test_motion_trigger_binary_sensor_behavior_last(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_binary_sensors: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test motion trigger fires when the last binary_sensor changes state."""
    await assert_trigger_behavior_last(
        hass,
        service_calls=service_calls,
        target_entities=target_binary_sensors,
        trigger_target_config=trigger_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        trigger=trigger,
        trigger_options=trigger_options,
        states=states,
    )


# --- Device class exclusion tests ---


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    (
        "trigger_key",
        "trigger_options",
        "initial_state",
        "target_state",
    ),
    [
        (
            "motion.detected",
            {},
            STATE_OFF,
            STATE_ON,
        ),
        (
            "motion.cleared",
            {},
            STATE_ON,
            STATE_OFF,
        ),
    ],
)
async def test_motion_trigger_excludes_non_motion_binary_sensor(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    trigger_key: str,
    trigger_options: dict[str, Any],
    initial_state: str,
    target_state: str,
) -> None:
    """Test motion trigger does not fire for entities without device_class motion."""
    entity_id_motion = "binary_sensor.test_motion"
    entity_id_occupancy = "binary_sensor.test_occupancy"

    # Set initial states
    hass.states.async_set(
        entity_id_motion, initial_state, {ATTR_DEVICE_CLASS: "motion"}
    )
    hass.states.async_set(
        entity_id_occupancy, initial_state, {ATTR_DEVICE_CLASS: "occupancy"}
    )
    await hass.async_block_till_done()

    await arm_trigger(
        hass,
        trigger_key,
        trigger_options,
        {
            CONF_ENTITY_ID: [
                entity_id_motion,
                entity_id_occupancy,
            ]
        },
    )

    # Motion binary_sensor changes - should trigger
    hass.states.async_set(entity_id_motion, target_state, {ATTR_DEVICE_CLASS: "motion"})
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data[CONF_ENTITY_ID] == entity_id_motion
    service_calls.clear()

    # Occupancy binary_sensor changes - should NOT trigger (wrong device class)
    hass.states.async_set(
        entity_id_occupancy, target_state, {ATTR_DEVICE_CLASS: "occupancy"}
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 0
