"""Test humidifier trigger."""

from contextlib import AbstractContextManager, nullcontext as does_not_raise
from typing import Any

import pytest
import voluptuous as vol

from homeassistant.components.humidifier.const import (
    ATTR_ACTION,
    HumidifierAction,
    HumidifierEntityFeature,
)
from homeassistant.components.humidifier.trigger import CONF_MODE
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
from homeassistant.helpers.trigger import async_validate_trigger_config

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
async def target_humidifiers(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple humidifier entities associated with different targets."""
    return await target_entities(hass, "humidifier")


@pytest.mark.parametrize(
    "trigger_key",
    [
        "humidifier.mode_changed",
        "humidifier.started_drying",
        "humidifier.started_humidifying",
        "humidifier.turned_off",
        "humidifier.turned_on",
    ],
)
async def test_humidifier_triggers_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, trigger_key: str
) -> None:
    """Test the humidifier triggers are gated by the labs flag."""
    await assert_trigger_gated_by_labs_flag(hass, caplog, trigger_key)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("humidifier"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="humidifier.turned_on",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
        ),
        *parametrize_trigger_states(
            trigger="humidifier.turned_off",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
        ),
    ],
)
async def test_humidifier_state_trigger_behavior_any(
    hass: HomeAssistant,
    target_humidifiers: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the humidifier state trigger fires when any humidifier state changes to a specific state."""
    await assert_trigger_behavior_any(
        hass,
        target_entities=target_humidifiers,
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
    parametrize_target_entities("humidifier"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="humidifier.started_drying",
            target_states=[(STATE_ON, {ATTR_ACTION: HumidifierAction.DRYING})],
            other_states=[(STATE_ON, {ATTR_ACTION: HumidifierAction.IDLE})],
        ),
        *parametrize_trigger_states(
            trigger="humidifier.started_humidifying",
            target_states=[(STATE_ON, {ATTR_ACTION: HumidifierAction.HUMIDIFYING})],
            other_states=[(STATE_ON, {ATTR_ACTION: HumidifierAction.IDLE})],
        ),
        *parametrize_trigger_states(
            trigger="humidifier.mode_changed",
            trigger_options={CONF_MODE: ["eco", "sleep"]},
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
            trigger_from_none=False,
        ),
    ],
)
async def test_humidifier_state_attribute_trigger_behavior_any(
    hass: HomeAssistant,
    target_humidifiers: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the humidifier state trigger fires when any humidifier state changes to a specific state."""
    await assert_trigger_behavior_any(
        hass,
        target_entities=target_humidifiers,
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
    parametrize_target_entities("humidifier"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="humidifier.turned_on",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
        ),
        *parametrize_trigger_states(
            trigger="humidifier.turned_off",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
        ),
    ],
)
async def test_humidifier_state_trigger_behavior_first(
    hass: HomeAssistant,
    target_humidifiers: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the humidifier state trigger fires when the first humidifier changes to a specific state."""
    await assert_trigger_behavior_first(
        hass,
        target_entities=target_humidifiers,
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
    parametrize_target_entities("humidifier"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="humidifier.started_drying",
            target_states=[(STATE_ON, {ATTR_ACTION: HumidifierAction.DRYING})],
            other_states=[(STATE_ON, {ATTR_ACTION: HumidifierAction.IDLE})],
        ),
        *parametrize_trigger_states(
            trigger="humidifier.started_humidifying",
            target_states=[(STATE_ON, {ATTR_ACTION: HumidifierAction.HUMIDIFYING})],
            other_states=[(STATE_ON, {ATTR_ACTION: HumidifierAction.IDLE})],
        ),
        *parametrize_trigger_states(
            trigger="humidifier.mode_changed",
            trigger_options={CONF_MODE: ["eco", "sleep"]},
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
            trigger_from_none=False,
        ),
    ],
)
async def test_humidifier_state_attribute_trigger_behavior_first(
    hass: HomeAssistant,
    target_humidifiers: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[tuple[tuple[str, dict], int]],
) -> None:
    """Test that the humidifier state trigger fires when the first humidifier state changes to a specific state."""
    await assert_trigger_behavior_first(
        hass,
        target_entities=target_humidifiers,
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
    parametrize_target_entities("humidifier"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="humidifier.turned_on",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
        ),
        *parametrize_trigger_states(
            trigger="humidifier.turned_off",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
        ),
    ],
)
async def test_humidifier_state_trigger_behavior_last(
    hass: HomeAssistant,
    target_humidifiers: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the humidifier state trigger fires when the last humidifier changes to a specific state."""
    await assert_trigger_behavior_last(
        hass,
        target_entities=target_humidifiers,
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
    parametrize_target_entities("humidifier"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="humidifier.started_drying",
            target_states=[(STATE_ON, {ATTR_ACTION: HumidifierAction.DRYING})],
            other_states=[(STATE_ON, {ATTR_ACTION: HumidifierAction.IDLE})],
        ),
        *parametrize_trigger_states(
            trigger="humidifier.started_humidifying",
            target_states=[(STATE_ON, {ATTR_ACTION: HumidifierAction.HUMIDIFYING})],
            other_states=[(STATE_ON, {ATTR_ACTION: HumidifierAction.IDLE})],
        ),
        *parametrize_trigger_states(
            trigger="humidifier.mode_changed",
            trigger_options={CONF_MODE: ["eco", "sleep"]},
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
            trigger_from_none=False,
        ),
    ],
)
async def test_humidifier_state_attribute_trigger_behavior_last(
    hass: HomeAssistant,
    target_humidifiers: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[tuple[tuple[str, dict], int]],
) -> None:
    """Test that the humidifier state trigger fires when the last humidifier state changes to a specific state."""
    await assert_trigger_behavior_last(
        hass,
        target_entities=target_humidifiers,
        trigger_target_config=trigger_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        trigger=trigger,
        trigger_options=trigger_options,
        states=states,
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "expected_result"),
    [
        # Valid configurations
        (
            "humidifier.mode_changed",
            {CONF_MODE: ["eco", "sleep"]},
            does_not_raise(),
        ),
        (
            "humidifier.mode_changed",
            {CONF_MODE: "eco"},
            does_not_raise(),
        ),
        # Invalid configurations
        (
            "humidifier.mode_changed",
            # Empty mode list
            {CONF_MODE: []},
            pytest.raises(vol.Invalid),
        ),
        (
            "humidifier.mode_changed",
            # Missing CONF_MODE
            {},
            pytest.raises(vol.Invalid),
        ),
    ],
)
async def test_humidifier_mode_changed_trigger_validation(
    hass: HomeAssistant,
    trigger: str,
    trigger_options: dict[str, Any],
    expected_result: AbstractContextManager,
) -> None:
    """Test humidifier mode_changed trigger config validation."""
    with expected_result:
        await async_validate_trigger_config(
            hass,
            [
                {
                    "platform": trigger,
                    CONF_TARGET: {CONF_ENTITY_ID: "humidifier.test"},
                    CONF_OPTIONS: trigger_options,
                }
            ],
        )
