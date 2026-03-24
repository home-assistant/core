"""Test battery conditions."""

from typing import Any

import pytest

from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant

from tests.components.common import (
    ConditionStateDescription,
    assert_condition_behavior_all,
    assert_condition_behavior_any,
    assert_condition_gated_by_labs_flag,
    parametrize_condition_states_all,
    parametrize_condition_states_any,
    parametrize_numerical_condition_above_below_all,
    parametrize_numerical_condition_above_below_any,
    parametrize_target_entities,
    target_entities,
)

_BATTERY_UNIT_ATTRS = {ATTR_UNIT_OF_MEASUREMENT: "%"}


@pytest.fixture
async def target_binary_sensors(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple binary sensor entities associated with different targets."""
    return await target_entities(hass, "binary_sensor")


@pytest.fixture
async def target_sensors(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple sensor entities associated with different targets."""
    return await target_entities(hass, "sensor")


@pytest.fixture
async def target_numbers(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple number entities associated with different targets."""
    return await target_entities(hass, "number")


@pytest.mark.parametrize(
    "condition",
    [
        "battery.is_low",
        "battery.is_not_low",
        "battery.is_charging",
        "battery.is_not_charging",
        "battery.is_level",
    ],
)
async def test_battery_conditions_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, condition: str
) -> None:
    """Test the battery conditions are gated by the labs flag."""
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
            condition="battery.is_low",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            required_filter_attributes={ATTR_DEVICE_CLASS: "battery"},
        ),
        *parametrize_condition_states_any(
            condition="battery.is_not_low",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            required_filter_attributes={ATTR_DEVICE_CLASS: "battery"},
        ),
        *parametrize_condition_states_any(
            condition="battery.is_charging",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            required_filter_attributes={ATTR_DEVICE_CLASS: "battery_charging"},
        ),
        *parametrize_condition_states_any(
            condition="battery.is_not_charging",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            required_filter_attributes={ATTR_DEVICE_CLASS: "battery_charging"},
        ),
    ],
)
async def test_battery_binary_condition_behavior_any(
    hass: HomeAssistant,
    target_binary_sensors: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the battery binary conditions with 'any' behavior."""
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
            condition="battery.is_low",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            required_filter_attributes={ATTR_DEVICE_CLASS: "battery"},
        ),
        *parametrize_condition_states_all(
            condition="battery.is_not_low",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            required_filter_attributes={ATTR_DEVICE_CLASS: "battery"},
        ),
        *parametrize_condition_states_all(
            condition="battery.is_charging",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            required_filter_attributes={ATTR_DEVICE_CLASS: "battery_charging"},
        ),
        *parametrize_condition_states_all(
            condition="battery.is_not_charging",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            required_filter_attributes={ATTR_DEVICE_CLASS: "battery_charging"},
        ),
    ],
)
async def test_battery_binary_condition_behavior_all(
    hass: HomeAssistant,
    target_binary_sensors: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the battery binary conditions with 'all' behavior."""
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


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("sensor"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    parametrize_numerical_condition_above_below_any(
        "battery.is_level",
        device_class="battery",
        unit_attributes=_BATTERY_UNIT_ATTRS,
    ),
)
async def test_battery_is_level_condition_behavior_any(
    hass: HomeAssistant,
    target_sensors: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the battery is_level condition with 'any' behavior."""
    await assert_condition_behavior_any(
        hass,
        target_entities=target_sensors,
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
    parametrize_target_entities("sensor"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    parametrize_numerical_condition_above_below_all(
        "battery.is_level",
        device_class="battery",
        unit_attributes=_BATTERY_UNIT_ATTRS,
    ),
)
async def test_battery_is_level_condition_behavior_all(
    hass: HomeAssistant,
    target_sensors: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the battery is_level condition with 'all' behavior."""
    await assert_condition_behavior_all(
        hass,
        target_entities=target_sensors,
        condition_target_config=condition_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        condition=condition,
        condition_options=condition_options,
        states=states,
    )
