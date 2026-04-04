"""Test person trigger."""

from typing import Any

import pytest

from homeassistant.components.person.const import DOMAIN
from homeassistant.const import STATE_HOME, STATE_NOT_HOME
from homeassistant.core import HomeAssistant

from tests.components.common import (
    TriggerStateDescription,
    assert_trigger_behavior_any,
    assert_trigger_behavior_first,
    assert_trigger_behavior_last,
    assert_trigger_gated_by_labs_flag,
    parametrize_target_entities,
    parametrize_trigger_states,
    target_entities,
)

STATE_WORK_ZONE = "work"


@pytest.fixture
async def target_persons(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple persons entities associated with different targets."""
    return await target_entities(hass, DOMAIN)


@pytest.mark.parametrize(
    "trigger_key",
    ["person.entered_home", "person.left_home"],
)
async def test_person_triggers_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, trigger_key: str
) -> None:
    """Test the person triggers are gated by the labs flag."""
    await assert_trigger_gated_by_labs_flag(hass, caplog, trigger_key)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities(DOMAIN),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="person.entered_home",
            target_states=[STATE_HOME],
            other_states=[STATE_NOT_HOME, STATE_WORK_ZONE],
        ),
        *parametrize_trigger_states(
            trigger="person.left_home",
            target_states=[STATE_NOT_HOME, STATE_WORK_ZONE],
            other_states=[STATE_HOME],
        ),
    ],
)
async def test_person_home_trigger_behavior_any(
    hass: HomeAssistant,
    target_persons: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the person home triggers when any person changes to a specific state."""
    await assert_trigger_behavior_any(
        hass,
        target_entities=target_persons,
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
    parametrize_target_entities(DOMAIN),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="person.entered_home",
            target_states=[STATE_HOME],
            other_states=[STATE_NOT_HOME, STATE_WORK_ZONE],
        ),
        *parametrize_trigger_states(
            trigger="person.left_home",
            target_states=[STATE_NOT_HOME, STATE_WORK_ZONE],
            other_states=[STATE_HOME],
        ),
    ],
)
async def test_person_state_trigger_behavior_first(
    hass: HomeAssistant,
    target_persons: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the person home triggers when the first person changes to a specific state."""
    await assert_trigger_behavior_first(
        hass,
        target_entities=target_persons,
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
    parametrize_target_entities(DOMAIN),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="person.entered_home",
            target_states=[STATE_HOME],
            other_states=[STATE_NOT_HOME, STATE_WORK_ZONE],
        ),
        *parametrize_trigger_states(
            trigger="person.left_home",
            target_states=[STATE_NOT_HOME, STATE_WORK_ZONE],
            other_states=[STATE_HOME],
        ),
    ],
)
async def test_person_state_trigger_behavior_last(
    hass: HomeAssistant,
    target_persons: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the person home triggers when the last person changes to a specific state."""
    await assert_trigger_behavior_last(
        hass,
        target_entities=target_persons,
        trigger_target_config=trigger_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        trigger=trigger,
        trigger_options=trigger_options,
        states=states,
    )
