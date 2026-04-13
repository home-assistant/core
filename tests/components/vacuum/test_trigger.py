"""Test vacuum triggers."""

from typing import Any

import pytest

from homeassistant.components.vacuum import VacuumActivity
from homeassistant.core import HomeAssistant

from tests.components.common import (
    TriggerStateDescription,
    assert_trigger_behavior_any,
    assert_trigger_behavior_first,
    assert_trigger_behavior_last,
    assert_trigger_gated_by_labs_flag,
    other_states,
    parametrize_target_entities,
    parametrize_trigger_states,
    target_entities,
)


@pytest.fixture
async def target_vacuums(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple vacuum entities associated with different targets."""
    return await target_entities(hass, "vacuum")


@pytest.mark.parametrize(
    "trigger_key",
    [
        "vacuum.docked",
        "vacuum.errored",
        "vacuum.paused_cleaning",
        "vacuum.started_cleaning",
        "vacuum.started_returning",
    ],
)
async def test_vacuum_triggers_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, trigger_key: str
) -> None:
    """Test the vacuum triggers are gated by the labs flag."""
    await assert_trigger_gated_by_labs_flag(hass, caplog, trigger_key)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("vacuum"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="vacuum.docked",
            target_states=[VacuumActivity.DOCKED],
            other_states=other_states(VacuumActivity.DOCKED),
        ),
        *parametrize_trigger_states(
            trigger="vacuum.errored",
            target_states=[VacuumActivity.ERROR],
            other_states=other_states(VacuumActivity.ERROR),
        ),
        *parametrize_trigger_states(
            trigger="vacuum.paused_cleaning",
            target_states=[VacuumActivity.PAUSED],
            other_states=other_states(VacuumActivity.PAUSED),
        ),
        *parametrize_trigger_states(
            trigger="vacuum.started_cleaning",
            target_states=[VacuumActivity.CLEANING],
            other_states=other_states(VacuumActivity.CLEANING),
        ),
        *parametrize_trigger_states(
            trigger="vacuum.started_returning",
            target_states=[VacuumActivity.RETURNING],
            other_states=other_states(VacuumActivity.RETURNING),
        ),
    ],
)
async def test_vacuum_state_trigger_behavior_any(
    hass: HomeAssistant,
    target_vacuums: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the vacuum state trigger fires when any vacuum state changes to a specific state."""
    await assert_trigger_behavior_any(
        hass,
        target_entities=target_vacuums,
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
    parametrize_target_entities("vacuum"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="vacuum.docked",
            target_states=[VacuumActivity.DOCKED],
            other_states=other_states(VacuumActivity.DOCKED),
        ),
        *parametrize_trigger_states(
            trigger="vacuum.errored",
            target_states=[VacuumActivity.ERROR],
            other_states=other_states(VacuumActivity.ERROR),
        ),
        *parametrize_trigger_states(
            trigger="vacuum.paused_cleaning",
            target_states=[VacuumActivity.PAUSED],
            other_states=other_states(VacuumActivity.PAUSED),
        ),
        *parametrize_trigger_states(
            trigger="vacuum.started_cleaning",
            target_states=[VacuumActivity.CLEANING],
            other_states=other_states(VacuumActivity.CLEANING),
        ),
        *parametrize_trigger_states(
            trigger="vacuum.started_returning",
            target_states=[VacuumActivity.RETURNING],
            other_states=other_states(VacuumActivity.RETURNING),
        ),
    ],
)
async def test_vacuum_state_trigger_behavior_first(
    hass: HomeAssistant,
    target_vacuums: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the vacuum state trigger fires when the first vacuum changes to a specific state."""
    await assert_trigger_behavior_first(
        hass,
        target_entities=target_vacuums,
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
    parametrize_target_entities("vacuum"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="vacuum.docked",
            target_states=[VacuumActivity.DOCKED],
            other_states=other_states(VacuumActivity.DOCKED),
        ),
        *parametrize_trigger_states(
            trigger="vacuum.errored",
            target_states=[VacuumActivity.ERROR],
            other_states=other_states(VacuumActivity.ERROR),
        ),
        *parametrize_trigger_states(
            trigger="vacuum.paused_cleaning",
            target_states=[VacuumActivity.PAUSED],
            other_states=other_states(VacuumActivity.PAUSED),
        ),
        *parametrize_trigger_states(
            trigger="vacuum.started_cleaning",
            target_states=[VacuumActivity.CLEANING],
            other_states=other_states(VacuumActivity.CLEANING),
        ),
        *parametrize_trigger_states(
            trigger="vacuum.started_returning",
            target_states=[VacuumActivity.RETURNING],
            other_states=other_states(VacuumActivity.RETURNING),
        ),
    ],
)
async def test_vacuum_state_trigger_behavior_last(
    hass: HomeAssistant,
    target_vacuums: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the vacuum state trigger fires when the last vacuum changes to a specific state."""
    await assert_trigger_behavior_last(
        hass,
        target_entities=target_vacuums,
        trigger_target_config=trigger_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        trigger=trigger,
        trigger_options=trigger_options,
        states=states,
    )
