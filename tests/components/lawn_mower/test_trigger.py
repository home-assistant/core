"""Test lawn mower triggers."""

from typing import Any

import pytest

from homeassistant.components.lawn_mower import LawnMowerActivity
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
async def target_lawn_mowers(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple lawn mower entities associated with different targets."""
    return await target_entities(hass, "lawn_mower")


@pytest.mark.parametrize(
    "trigger_key",
    [
        "lawn_mower.docked",
        "lawn_mower.errored",
        "lawn_mower.paused_mowing",
        "lawn_mower.started_mowing",
        "lawn_mower.started_returning",
    ],
)
async def test_lawn_mower_triggers_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, trigger_key: str
) -> None:
    """Test the lawn mower triggers are gated by the labs flag."""
    await assert_trigger_gated_by_labs_flag(hass, caplog, trigger_key)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("lawn_mower"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="lawn_mower.docked",
            target_states=[LawnMowerActivity.DOCKED],
            other_states=other_states(LawnMowerActivity.DOCKED),
        ),
        *parametrize_trigger_states(
            trigger="lawn_mower.errored",
            target_states=[LawnMowerActivity.ERROR],
            other_states=other_states(LawnMowerActivity.ERROR),
        ),
        *parametrize_trigger_states(
            trigger="lawn_mower.paused_mowing",
            target_states=[LawnMowerActivity.PAUSED],
            other_states=other_states(LawnMowerActivity.PAUSED),
        ),
        *parametrize_trigger_states(
            trigger="lawn_mower.started_mowing",
            target_states=[LawnMowerActivity.MOWING],
            other_states=other_states(LawnMowerActivity.MOWING),
        ),
        *parametrize_trigger_states(
            trigger="lawn_mower.started_returning",
            target_states=[LawnMowerActivity.RETURNING],
            other_states=other_states(LawnMowerActivity.RETURNING),
        ),
    ],
)
async def test_lawn_mower_state_trigger_behavior_any(
    hass: HomeAssistant,
    target_lawn_mowers: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the lawn mower state trigger fires when any lawn mower state changes to a specific state."""
    await assert_trigger_behavior_any(
        hass,
        target_entities=target_lawn_mowers,
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
    parametrize_target_entities("lawn_mower"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="lawn_mower.docked",
            target_states=[LawnMowerActivity.DOCKED],
            other_states=other_states(LawnMowerActivity.DOCKED),
        ),
        *parametrize_trigger_states(
            trigger="lawn_mower.errored",
            target_states=[LawnMowerActivity.ERROR],
            other_states=other_states(LawnMowerActivity.ERROR),
        ),
        *parametrize_trigger_states(
            trigger="lawn_mower.paused_mowing",
            target_states=[LawnMowerActivity.PAUSED],
            other_states=other_states(LawnMowerActivity.PAUSED),
        ),
        *parametrize_trigger_states(
            trigger="lawn_mower.started_mowing",
            target_states=[LawnMowerActivity.MOWING],
            other_states=other_states(LawnMowerActivity.MOWING),
        ),
        *parametrize_trigger_states(
            trigger="lawn_mower.started_returning",
            target_states=[LawnMowerActivity.RETURNING],
            other_states=other_states(LawnMowerActivity.RETURNING),
        ),
    ],
)
async def test_lawn_mower_state_trigger_behavior_first(
    hass: HomeAssistant,
    target_lawn_mowers: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the lawn mower state trigger fires when the first lawn mower changes to a specific state."""
    await assert_trigger_behavior_first(
        hass,
        target_entities=target_lawn_mowers,
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
    parametrize_target_entities("lawn_mower"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="lawn_mower.docked",
            target_states=[LawnMowerActivity.DOCKED],
            other_states=other_states(LawnMowerActivity.DOCKED),
        ),
        *parametrize_trigger_states(
            trigger="lawn_mower.errored",
            target_states=[LawnMowerActivity.ERROR],
            other_states=other_states(LawnMowerActivity.ERROR),
        ),
        *parametrize_trigger_states(
            trigger="lawn_mower.paused_mowing",
            target_states=[LawnMowerActivity.PAUSED],
            other_states=other_states(LawnMowerActivity.PAUSED),
        ),
        *parametrize_trigger_states(
            trigger="lawn_mower.started_mowing",
            target_states=[LawnMowerActivity.MOWING],
            other_states=other_states(LawnMowerActivity.MOWING),
        ),
        *parametrize_trigger_states(
            trigger="lawn_mower.started_returning",
            target_states=[LawnMowerActivity.RETURNING],
            other_states=other_states(LawnMowerActivity.RETURNING),
        ),
    ],
)
async def test_lawn_mower_state_trigger_behavior_last(
    hass: HomeAssistant,
    target_lawn_mowers: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the lawn_mower state trigger fires when the last lawn_mower changes to a specific state."""
    await assert_trigger_behavior_last(
        hass,
        target_entities=target_lawn_mowers,
        trigger_target_config=trigger_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        trigger=trigger,
        trigger_options=trigger_options,
        states=states,
    )
