"""Test vacuum conditions."""

from typing import Any

import pytest

from homeassistant.components.vacuum import VacuumActivity
from homeassistant.core import HomeAssistant

from tests.components.common import (
    ConditionStateDescription,
    assert_condition_behavior_all,
    assert_condition_behavior_any,
    assert_condition_gated_by_labs_flag,
    assert_condition_options_supported,
    other_states,
    parametrize_condition_states_all,
    parametrize_condition_states_any,
    parametrize_target_entities,
    target_entities,
)


@pytest.fixture
async def target_vacuums(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple vacuum entities associated with different targets."""
    return await target_entities(hass, "vacuum")


@pytest.mark.parametrize(
    "condition",
    [
        "vacuum.is_cleaning",
        "vacuum.is_docked",
        "vacuum.is_encountering_an_error",
        "vacuum.is_paused",
        "vacuum.is_returning",
    ],
)
async def test_vacuum_conditions_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, condition: str
) -> None:
    """Test the vacuum conditions are gated by the labs flag."""
    await assert_condition_gated_by_labs_flag(hass, caplog, condition)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_key", "base_options", "supports_behavior", "supports_duration"),
    [
        ("vacuum.is_cleaning", {}, True, True),
        ("vacuum.is_docked", {}, True, True),
        ("vacuum.is_encountering_an_error", {}, True, True),
        ("vacuum.is_paused", {}, True, True),
        ("vacuum.is_returning", {}, True, True),
    ],
)
async def test_vacuum_condition_options_validation(
    hass: HomeAssistant,
    condition_key: str,
    base_options: dict[str, Any] | None,
    supports_behavior: bool,
    supports_duration: bool,
) -> None:
    """Test that vacuum conditions support the expected options."""
    await assert_condition_options_supported(
        hass,
        condition_key,
        base_options,
        supports_behavior=supports_behavior,
        supports_duration=supports_duration,
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("vacuum"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_any(
            condition="vacuum.is_cleaning",
            target_states=[VacuumActivity.CLEANING],
            other_states=other_states(VacuumActivity.CLEANING),
        ),
        *parametrize_condition_states_any(
            condition="vacuum.is_docked",
            target_states=[VacuumActivity.DOCKED],
            other_states=other_states(VacuumActivity.DOCKED),
        ),
        *parametrize_condition_states_any(
            condition="vacuum.is_encountering_an_error",
            target_states=[VacuumActivity.ERROR],
            other_states=other_states(VacuumActivity.ERROR),
        ),
        *parametrize_condition_states_any(
            condition="vacuum.is_paused",
            target_states=[VacuumActivity.PAUSED],
            other_states=other_states(VacuumActivity.PAUSED),
        ),
        *parametrize_condition_states_any(
            condition="vacuum.is_returning",
            target_states=[VacuumActivity.RETURNING],
            other_states=other_states(VacuumActivity.RETURNING),
        ),
    ],
)
async def test_vacuum_state_condition_behavior_any(
    hass: HomeAssistant,
    target_vacuums: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the vacuum state condition with the 'any' behavior."""
    await assert_condition_behavior_any(
        hass,
        target_entities=target_vacuums,
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
    parametrize_target_entities("vacuum"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_all(
            condition="vacuum.is_cleaning",
            target_states=[VacuumActivity.CLEANING],
            other_states=other_states(VacuumActivity.CLEANING),
        ),
        *parametrize_condition_states_all(
            condition="vacuum.is_docked",
            target_states=[VacuumActivity.DOCKED],
            other_states=other_states(VacuumActivity.DOCKED),
        ),
        *parametrize_condition_states_all(
            condition="vacuum.is_encountering_an_error",
            target_states=[VacuumActivity.ERROR],
            other_states=other_states(VacuumActivity.ERROR),
        ),
        *parametrize_condition_states_all(
            condition="vacuum.is_paused",
            target_states=[VacuumActivity.PAUSED],
            other_states=other_states(VacuumActivity.PAUSED),
        ),
        *parametrize_condition_states_all(
            condition="vacuum.is_returning",
            target_states=[VacuumActivity.RETURNING],
            other_states=other_states(VacuumActivity.RETURNING),
        ),
    ],
)
async def test_vacuum_state_condition_behavior_all(
    hass: HomeAssistant,
    target_vacuums: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the vacuum state condition with the 'all' behavior."""
    await assert_condition_behavior_all(
        hass,
        target_entities=target_vacuums,
        condition_target_config=condition_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        condition=condition,
        condition_options=condition_options,
        states=states,
    )
