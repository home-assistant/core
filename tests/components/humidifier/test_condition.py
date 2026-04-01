"""Test humidifier conditions."""

from contextlib import AbstractContextManager, nullcontext as does_not_raise
from typing import Any

import pytest
import voluptuous as vol

from homeassistant.components.humidifier.condition import CONF_MODE
from homeassistant.components.humidifier.const import (
    ATTR_ACTION,
    ATTR_HUMIDITY,
    HumidifierAction,
    HumidifierEntityFeature,
)
from homeassistant.const import (
    ATTR_MODE,
    ATTR_SUPPORTED_FEATURES,
    CONF_ENTITY_ID,
    CONF_OPTIONS,
    CONF_TARGET,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.condition import async_validate_condition_config

from tests.components.common import (
    ConditionStateDescription,
    assert_condition_behavior_all,
    assert_condition_behavior_any,
    assert_condition_gated_by_labs_flag,
    parametrize_condition_states_all,
    parametrize_condition_states_any,
    parametrize_numerical_attribute_condition_above_below_all,
    parametrize_numerical_attribute_condition_above_below_any,
    parametrize_target_entities,
    target_entities,
)


@pytest.fixture
async def target_humidifiers(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple humidifier entities associated with different targets."""
    return await target_entities(hass, "humidifier")


@pytest.mark.parametrize(
    "condition",
    [
        "humidifier.is_off",
        "humidifier.is_on",
        "humidifier.is_drying",
        "humidifier.is_humidifying",
        "humidifier.is_mode",
        "humidifier.is_target_humidity",
    ],
)
async def test_humidifier_conditions_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, condition: str
) -> None:
    """Test the humidifier conditions are gated by the labs flag."""
    await assert_condition_gated_by_labs_flag(hass, caplog, condition)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("humidifier"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_any(
            condition="humidifier.is_off",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
        ),
        *parametrize_condition_states_any(
            condition="humidifier.is_on",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
        ),
    ],
)
async def test_humidifier_state_condition_behavior_any(
    hass: HomeAssistant,
    target_humidifiers: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the humidifier state condition with the 'any' behavior."""
    await assert_condition_behavior_any(
        hass,
        target_entities=target_humidifiers,
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
    parametrize_target_entities("humidifier"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_all(
            condition="humidifier.is_off",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
        ),
        *parametrize_condition_states_all(
            condition="humidifier.is_on",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
        ),
    ],
)
async def test_humidifier_state_condition_behavior_all(
    hass: HomeAssistant,
    target_humidifiers: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the humidifier state condition with the 'all' behavior."""
    await assert_condition_behavior_all(
        hass,
        target_entities=target_humidifiers,
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
    parametrize_target_entities("humidifier"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_any(
            condition="humidifier.is_drying",
            target_states=[(STATE_ON, {ATTR_ACTION: HumidifierAction.DRYING})],
            other_states=[(STATE_ON, {ATTR_ACTION: HumidifierAction.IDLE})],
        ),
        *parametrize_condition_states_any(
            condition="humidifier.is_humidifying",
            target_states=[(STATE_ON, {ATTR_ACTION: HumidifierAction.HUMIDIFYING})],
            other_states=[(STATE_ON, {ATTR_ACTION: HumidifierAction.IDLE})],
        ),
        *parametrize_condition_states_any(
            condition="humidifier.is_mode",
            condition_options={CONF_MODE: ["eco", "sleep"]},
            target_states=[
                (STATE_ON, {ATTR_MODE: "eco"}),
                (STATE_ON, {ATTR_MODE: "sleep"}),
            ],
            other_states=[
                (STATE_ON, {ATTR_MODE: "normal"}),
            ],
            required_filter_attributes={
                ATTR_SUPPORTED_FEATURES: HumidifierEntityFeature.MODES
            },
        ),
    ],
)
async def test_humidifier_attribute_condition_behavior_any(
    hass: HomeAssistant,
    target_humidifiers: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the humidifier attribute condition with the 'any' behavior."""
    await assert_condition_behavior_any(
        hass,
        target_entities=target_humidifiers,
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
    parametrize_target_entities("humidifier"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_all(
            condition="humidifier.is_drying",
            target_states=[(STATE_ON, {ATTR_ACTION: HumidifierAction.DRYING})],
            other_states=[(STATE_ON, {ATTR_ACTION: HumidifierAction.IDLE})],
        ),
        *parametrize_condition_states_all(
            condition="humidifier.is_humidifying",
            target_states=[(STATE_ON, {ATTR_ACTION: HumidifierAction.HUMIDIFYING})],
            other_states=[(STATE_ON, {ATTR_ACTION: HumidifierAction.IDLE})],
        ),
        *parametrize_condition_states_all(
            condition="humidifier.is_mode",
            condition_options={CONF_MODE: ["eco", "sleep"]},
            target_states=[
                (STATE_ON, {ATTR_MODE: "eco"}),
                (STATE_ON, {ATTR_MODE: "sleep"}),
            ],
            other_states=[
                (STATE_ON, {ATTR_MODE: "normal"}),
            ],
            required_filter_attributes={
                ATTR_SUPPORTED_FEATURES: HumidifierEntityFeature.MODES
            },
        ),
    ],
)
async def test_humidifier_attribute_condition_behavior_all(
    hass: HomeAssistant,
    target_humidifiers: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the humidifier attribute condition with the 'all' behavior."""
    await assert_condition_behavior_all(
        hass,
        target_entities=target_humidifiers,
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
    parametrize_target_entities("humidifier"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    parametrize_numerical_attribute_condition_above_below_any(
        "humidifier.is_target_humidity",
        STATE_ON,
        ATTR_HUMIDITY,
    ),
)
async def test_humidifier_numerical_condition_behavior_any(
    hass: HomeAssistant,
    target_humidifiers: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the humidifier numerical condition with the 'any' behavior."""
    await assert_condition_behavior_any(
        hass,
        target_entities=target_humidifiers,
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
    parametrize_target_entities("humidifier"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    parametrize_numerical_attribute_condition_above_below_all(
        "humidifier.is_target_humidity",
        STATE_ON,
        ATTR_HUMIDITY,
    ),
)
async def test_humidifier_numerical_condition_behavior_all(
    hass: HomeAssistant,
    target_humidifiers: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the humidifier numerical condition with the 'all' behavior."""
    await assert_condition_behavior_all(
        hass,
        target_entities=target_humidifiers,
        condition_target_config=condition_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        condition=condition,
        condition_options=condition_options,
        states=states,
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition", "condition_options", "expected_result"),
    [
        # Valid configurations
        (
            "humidifier.is_mode",
            {CONF_MODE: ["eco", "sleep"]},
            does_not_raise(),
        ),
        (
            "humidifier.is_mode",
            {CONF_MODE: "eco"},
            does_not_raise(),
        ),
        # Invalid configurations
        (
            "humidifier.is_mode",
            # Empty mode list
            {CONF_MODE: []},
            pytest.raises(vol.Invalid),
        ),
        (
            "humidifier.is_mode",
            # Missing CONF_MODE
            {},
            pytest.raises(vol.Invalid),
        ),
    ],
)
async def test_humidifier_is_mode_condition_validation(
    hass: HomeAssistant,
    condition: str,
    condition_options: dict[str, Any],
    expected_result: AbstractContextManager,
) -> None:
    """Test humidifier is_mode condition config validation."""
    with expected_result:
        await async_validate_condition_config(
            hass,
            {
                "condition": condition,
                CONF_TARGET: {CONF_ENTITY_ID: "humidifier.test"},
                CONF_OPTIONS: condition_options,
            },
        )
