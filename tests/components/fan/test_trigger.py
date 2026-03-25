"""Test fan trigger."""

from typing import Any

import pytest

from homeassistant.const import STATE_OFF, STATE_ON
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


@pytest.fixture
async def target_fans(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple fan entities associated with different targets."""
    return await target_entities(hass, "fan")


@pytest.mark.parametrize(
    "trigger_key",
    [
        "fan.turned_off",
        "fan.turned_on",
    ],
)
async def test_fan_triggers_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, trigger_key: str
) -> None:
    """Test the fan triggers are gated by the labs flag."""
    await assert_trigger_gated_by_labs_flag(hass, caplog, trigger_key)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("fan"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="fan.turned_on",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
        ),
        *parametrize_trigger_states(
            trigger="fan.turned_off",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
        ),
    ],
)
async def test_fan_state_trigger_behavior_any(
    hass: HomeAssistant,
    target_fans: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the fan state trigger fires when any fan state changes to a specific state."""
    await assert_trigger_behavior_any(
        hass,
        target_entities=target_fans,
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
    parametrize_target_entities("fan"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="fan.turned_on",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
        ),
        *parametrize_trigger_states(
            trigger="fan.turned_off",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
        ),
    ],
)
async def test_fan_state_trigger_behavior_first(
    hass: HomeAssistant,
    target_fans: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the fan state trigger fires when the first fan changes to a specific state."""
    await assert_trigger_behavior_first(
        hass,
        target_entities=target_fans,
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
    parametrize_target_entities("fan"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="fan.turned_on",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
        ),
        *parametrize_trigger_states(
            trigger="fan.turned_off",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
        ),
    ],
)
async def test_fan_state_trigger_behavior_last(
    hass: HomeAssistant,
    target_fans: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the fan state trigger fires when the last fan changes to a specific state."""
    await assert_trigger_behavior_last(
        hass,
        target_entities=target_fans,
        trigger_target_config=trigger_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        trigger=trigger,
        trigger_options=trigger_options,
        states=states,
    )
