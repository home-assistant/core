"""Test weather trigger."""

from contextlib import AbstractContextManager, nullcontext as does_not_raise
from typing import Any

import probatio
import pytest
from pytest_homeassistant.components.common import (
    TargetSupport,
    TriggerStateDescription,
    assert_trigger_behavior_each,
    assert_trigger_options_supported,
    assert_triggers_target_support,
    parametrize_target_entities,
    parametrize_trigger_states,
    target_entities,
)

from homeassistant.components.weather.const import ALL_CONDITIONS, RAIN_CONDITIONS
from homeassistant.components.weather.trigger import CONF_CONDITION, TRIGGERS
from homeassistant.const import CONF_ENTITY_ID, CONF_OPTIONS, CONF_TARGET
from homeassistant.core import HomeAssistant
from homeassistant.helpers.trigger import async_validate_trigger_config

_NON_RAIN_CONDITIONS = [
    condition for condition in ALL_CONDITIONS if condition not in RAIN_CONDITIONS
]
_CONDITION_CHANGED_TARGETS = ["rainy", "pouring"]
_CONDITION_CHANGED_OTHERS = [
    condition
    for condition in ALL_CONDITIONS
    if condition not in _CONDITION_CHANGED_TARGETS
]


@pytest.fixture
async def target_weathers(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple weather entities associated with different targets."""
    return await target_entities(hass, "weather")


_TRIGGER_TARGET_SUPPORT: dict[str, TargetSupport] = {
    "condition_changed": TargetSupport.STANDARD,
    "started_raining": TargetSupport.STANDARD,
    "stopped_raining": TargetSupport.STANDARD,
}


@pytest.mark.parametrize(
    ("trigger_key", "base_options", "supports_behavior", "supports_duration"),
    [
        ("weather.started_raining", {}, True, True),
        ("weather.stopped_raining", {}, True, True),
        (
            "weather.condition_changed",
            {CONF_CONDITION: ["rainy", "pouring"]},
            True,
            True,
        ),
    ],
)
async def test_weather_trigger_options_validation(
    hass: HomeAssistant,
    trigger_key: str,
    base_options: dict[str, Any] | None,
    supports_behavior: bool,
    supports_duration: bool,
) -> None:
    """Test that weather triggers support the expected options."""
    await assert_trigger_options_supported(
        hass,
        trigger_key,
        base_options,
        supports_behavior=supports_behavior,
        supports_duration=supports_duration,
    )


def test_trigger_target_support() -> None:
    """Certify the trigger registry matches its declared target support."""
    assert_triggers_target_support(TRIGGERS, _TRIGGER_TARGET_SUPPORT)


@pytest.mark.parametrize(
    ("trigger", "trigger_options", "expected_result"),
    [
        # Valid configurations
        (
            "weather.condition_changed",
            {CONF_CONDITION: ["rainy", "pouring"]},
            does_not_raise(),
        ),
        (
            "weather.condition_changed",
            {CONF_CONDITION: "rainy"},
            does_not_raise(),
        ),
        # Invalid configurations
        (
            "weather.condition_changed",
            # Empty condition list
            {CONF_CONDITION: []},
            pytest.raises(probatio.Invalid),
        ),
        (
            "weather.condition_changed",
            # Missing CONF_CONDITION
            {},
            pytest.raises(probatio.Invalid),
        ),
        (
            "weather.condition_changed",
            {CONF_CONDITION: ["invalid_condition"]},
            pytest.raises(probatio.Invalid),
        ),
    ],
)
async def test_weather_trigger_validation(
    hass: HomeAssistant,
    trigger: str,
    trigger_options: dict[str, Any],
    expected_result: AbstractContextManager,
) -> None:
    """Test weather trigger config validation."""
    with expected_result:
        await async_validate_trigger_config(
            hass,
            [
                {
                    "platform": trigger,
                    CONF_TARGET: {CONF_ENTITY_ID: "weather.test_weather"},
                    CONF_OPTIONS: trigger_options,
                }
            ],
        )


@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("weather"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="weather.condition_changed",
            trigger_options={CONF_CONDITION: _CONDITION_CHANGED_TARGETS},
            target_states=_CONDITION_CHANGED_TARGETS,
            other_states=_CONDITION_CHANGED_OTHERS,
            retrigger_on_target_state=True,
        ),
        *parametrize_trigger_states(
            trigger="weather.started_raining",
            target_states=sorted(RAIN_CONDITIONS),
            other_states=_NON_RAIN_CONDITIONS,
        ),
        *parametrize_trigger_states(
            trigger="weather.stopped_raining",
            target_states=_NON_RAIN_CONDITIONS,
            other_states=sorted(RAIN_CONDITIONS),
        ),
    ],
)
async def test_weather_trigger_behavior_each(
    hass: HomeAssistant,
    target_weathers: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test weather trigger fires on the expected condition changes."""
    await assert_trigger_behavior_each(
        hass,
        target_entities=target_weathers,
        trigger_target_config=trigger_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        trigger=trigger,
        trigger_options=trigger_options,
        states=states,
    )
