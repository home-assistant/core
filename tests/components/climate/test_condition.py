"""Test climate conditions."""

from typing import Any

import pytest

from homeassistant.components.climate.const import (
    ATTR_HVAC_ACTION,
    HVACAction,
    HVACMode,
)
from homeassistant.core import HomeAssistant

from tests.components.common import (
    ConditionStateDescription,
    assert_condition_behavior_all,
    assert_condition_behavior_any,
    assert_condition_gated_by_labs_flag,
    other_states,
    parametrize_condition_states_all,
    parametrize_condition_states_any,
    parametrize_target_entities,
    target_entities,
)


@pytest.fixture
async def target_climates(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple climate entities associated with different targets."""
    return await target_entities(hass, "climate")


@pytest.mark.parametrize(
    "condition",
    [
        "climate.is_off",
        "climate.is_on",
        "climate.is_cooling",
        "climate.is_drying",
        "climate.is_heating",
    ],
)
async def test_climate_conditions_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, condition: str
) -> None:
    """Test the climate conditions are gated by the labs flag."""
    await assert_condition_gated_by_labs_flag(hass, caplog, condition)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("climate"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_any(
            condition="climate.is_off",
            target_states=[HVACMode.OFF],
            other_states=other_states(HVACMode.OFF),
        ),
        *parametrize_condition_states_any(
            condition="climate.is_on",
            target_states=[
                HVACMode.AUTO,
                HVACMode.COOL,
                HVACMode.DRY,
                HVACMode.FAN_ONLY,
                HVACMode.HEAT,
                HVACMode.HEAT_COOL,
            ],
            other_states=[HVACMode.OFF],
        ),
    ],
)
async def test_climate_state_condition_behavior_any(
    hass: HomeAssistant,
    target_climates: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the climate state condition with the 'any' behavior."""
    await assert_condition_behavior_any(
        hass,
        target_entities=target_climates,
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
    parametrize_target_entities("climate"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_all(
            condition="climate.is_off",
            target_states=[HVACMode.OFF],
            other_states=other_states(HVACMode.OFF),
        ),
        *parametrize_condition_states_all(
            condition="climate.is_on",
            target_states=[
                HVACMode.AUTO,
                HVACMode.COOL,
                HVACMode.DRY,
                HVACMode.FAN_ONLY,
                HVACMode.HEAT,
                HVACMode.HEAT_COOL,
            ],
            other_states=[HVACMode.OFF],
        ),
    ],
)
async def test_climate_state_condition_behavior_all(
    hass: HomeAssistant,
    target_climates: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the climate state condition with the 'all' behavior."""
    await assert_condition_behavior_all(
        hass,
        target_entities=target_climates,
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
    parametrize_target_entities("climate"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_any(
            condition="climate.is_cooling",
            target_states=[(HVACMode.AUTO, {ATTR_HVAC_ACTION: HVACAction.COOLING})],
            other_states=[(HVACMode.AUTO, {ATTR_HVAC_ACTION: HVACAction.IDLE})],
        ),
        *parametrize_condition_states_any(
            condition="climate.is_drying",
            target_states=[(HVACMode.AUTO, {ATTR_HVAC_ACTION: HVACAction.DRYING})],
            other_states=[(HVACMode.AUTO, {ATTR_HVAC_ACTION: HVACAction.IDLE})],
        ),
        *parametrize_condition_states_any(
            condition="climate.is_heating",
            target_states=[(HVACMode.AUTO, {ATTR_HVAC_ACTION: HVACAction.HEATING})],
            other_states=[(HVACMode.AUTO, {ATTR_HVAC_ACTION: HVACAction.IDLE})],
        ),
    ],
)
async def test_climate_attribute_condition_behavior_any(
    hass: HomeAssistant,
    target_climates: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the climate attribute condition with the 'any' behavior."""
    await assert_condition_behavior_any(
        hass,
        target_entities=target_climates,
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
    parametrize_target_entities("climate"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_all(
            condition="climate.is_cooling",
            target_states=[(HVACMode.AUTO, {ATTR_HVAC_ACTION: HVACAction.COOLING})],
            other_states=[(HVACMode.AUTO, {ATTR_HVAC_ACTION: HVACAction.IDLE})],
        ),
        *parametrize_condition_states_all(
            condition="climate.is_drying",
            target_states=[(HVACMode.AUTO, {ATTR_HVAC_ACTION: HVACAction.DRYING})],
            other_states=[(HVACMode.AUTO, {ATTR_HVAC_ACTION: HVACAction.IDLE})],
        ),
        *parametrize_condition_states_all(
            condition="climate.is_heating",
            target_states=[(HVACMode.AUTO, {ATTR_HVAC_ACTION: HVACAction.HEATING})],
            other_states=[(HVACMode.AUTO, {ATTR_HVAC_ACTION: HVACAction.IDLE})],
        ),
    ],
)
async def test_climate_attribute_condition_behavior_all(
    hass: HomeAssistant,
    target_climates: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the climate attribute condition with the 'all' behavior."""
    await assert_condition_behavior_all(
        hass,
        target_entities=target_climates,
        condition_target_config=condition_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        condition=condition,
        condition_options=condition_options,
        states=states,
    )
