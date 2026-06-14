"""Test light trigger."""

from typing import Any

import pytest

from homeassistant.components.light import ATTR_BRIGHTNESS
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from tests.components.common import (
    TriggerStateDescription,
    assert_trigger_behavior_all,
    assert_trigger_behavior_each,
    assert_trigger_behavior_first,
    assert_trigger_gated_by_labs_flag,
    assert_trigger_ignores_limit_entities_with_wrong_unit,
    assert_trigger_options_supported,
    parametrize_numerical_attribute_changed_trigger_states,
    parametrize_numerical_attribute_crossed_threshold_trigger_states,
    parametrize_target_entities,
    parametrize_trigger_states,
    target_entities,
)

# Brightness is stored as a uint8 (0-255) but the trigger threshold is in
# percent (0-100). The generic numerical-attribute helpers feed values in
# the threshold's percent space and scale them by `attribute_value_scale`
# to land on the entity's storage values; for brightness that's
# 255/100 = 2.55 (so 0/50/60/100 -> 0/127.5/153/255).
_BRIGHTNESS_VALUE_SCALE = 255 / 100


@pytest.fixture
async def target_lights(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple light entities associated with different targets."""
    return await target_entities(hass, "light")


@pytest.mark.parametrize(
    "trigger_key",
    [
        "light.brightness_changed",
        "light.brightness_crossed_threshold",
        "light.turned_off",
        "light.turned_on",
    ],
)
async def test_light_triggers_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, trigger_key: str
) -> None:
    """Test the light triggers are gated by the labs flag."""
    await assert_trigger_gated_by_labs_flag(hass, caplog, trigger_key)


_CHANGED_THRESHOLD = {"threshold": {"type": "any"}}
_BRIGHTNESS_CROSSED_THRESHOLD = {
    "threshold": {"type": "above", "value": {"number": 50}}
}


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_key", "base_options", "supports_behavior", "supports_duration"),
    [
        ("light.turned_on", {}, True, True),
        ("light.turned_off", {}, True, True),
        ("light.brightness_changed", _CHANGED_THRESHOLD, False, False),
        (
            "light.brightness_crossed_threshold",
            _BRIGHTNESS_CROSSED_THRESHOLD,
            True,
            True,
        ),
    ],
)
async def test_light_trigger_options_validation(
    hass: HomeAssistant,
    trigger_key: str,
    base_options: dict[str, Any] | None,
    supports_behavior: bool,
    supports_duration: bool,
) -> None:
    """Test that light triggers support the expected options."""
    await assert_trigger_options_supported(
        hass,
        trigger_key,
        base_options,
        supports_behavior=supports_behavior,
        supports_duration=supports_duration,
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("light"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="light.turned_on",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
        ),
        *parametrize_trigger_states(
            trigger="light.turned_off",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
        ),
    ],
)
async def test_light_state_trigger_behavior_each(
    hass: HomeAssistant,
    target_lights: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test light trigger fires when any light changes state."""
    await assert_trigger_behavior_each(
        hass,
        target_entities=target_lights,
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
    parametrize_target_entities("light"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_numerical_attribute_changed_trigger_states(
            "light.brightness_changed",
            STATE_ON,
            ATTR_BRIGHTNESS,
            attribute_value_scale=_BRIGHTNESS_VALUE_SCALE,
        ),
        *parametrize_numerical_attribute_crossed_threshold_trigger_states(
            "light.brightness_crossed_threshold",
            STATE_ON,
            ATTR_BRIGHTNESS,
            attribute_value_scale=_BRIGHTNESS_VALUE_SCALE,
        ),
    ],
)
async def test_light_state_attribute_trigger_behavior_each(
    hass: HomeAssistant,
    target_lights: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test light trigger fires when any light changes state."""
    await assert_trigger_behavior_each(
        hass,
        target_entities=target_lights,
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
    parametrize_target_entities("light"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="light.turned_on",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
        ),
        *parametrize_trigger_states(
            trigger="light.turned_off",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
        ),
    ],
)
async def test_light_state_trigger_behavior_first(
    hass: HomeAssistant,
    target_lights: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test light trigger fires when first light changes state."""
    await assert_trigger_behavior_first(
        hass,
        target_entities=target_lights,
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
    parametrize_target_entities("light"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_numerical_attribute_crossed_threshold_trigger_states(
            "light.brightness_crossed_threshold",
            STATE_ON,
            ATTR_BRIGHTNESS,
            attribute_value_scale=_BRIGHTNESS_VALUE_SCALE,
        ),
    ],
)
async def test_light_state_attribute_trigger_behavior_first(
    hass: HomeAssistant,
    target_lights: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[tuple[tuple[str, dict], int]],
) -> None:
    """Test light trigger fires on first light state change."""
    await assert_trigger_behavior_first(
        hass,
        target_entities=target_lights,
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
    parametrize_target_entities("light"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="light.turned_on",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
        ),
        *parametrize_trigger_states(
            trigger="light.turned_off",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
        ),
    ],
)
async def test_light_state_trigger_behavior_all(
    hass: HomeAssistant,
    target_lights: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test light trigger fires when last light changes state."""
    await assert_trigger_behavior_all(
        hass,
        target_entities=target_lights,
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
    parametrize_target_entities("light"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_numerical_attribute_crossed_threshold_trigger_states(
            "light.brightness_crossed_threshold",
            STATE_ON,
            ATTR_BRIGHTNESS,
            attribute_value_scale=_BRIGHTNESS_VALUE_SCALE,
        ),
    ],
)
async def test_light_state_attribute_trigger_behavior_all(
    hass: HomeAssistant,
    target_lights: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[tuple[tuple[str, dict], int]],
) -> None:
    """Test light trigger fires when all lights have changed state."""
    await assert_trigger_behavior_all(
        hass,
        target_entities=target_lights,
        trigger_target_config=trigger_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        trigger=trigger,
        trigger_options=trigger_options,
        states=states,
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "limit_entities"),
    [
        (
            "light.brightness_changed",
            {
                "threshold": {
                    "type": "between",
                    "value_min": {"entity": "sensor.brightness_above"},
                    "value_max": {"entity": "sensor.brightness_below"},
                },
            },
            ["sensor.brightness_above", "sensor.brightness_below"],
        ),
        (
            "light.brightness_crossed_threshold",
            {
                "threshold": {
                    "type": "between",
                    "value_min": {"entity": "sensor.brightness_lower"},
                    "value_max": {"entity": "sensor.brightness_upper"},
                },
            },
            ["sensor.brightness_lower", "sensor.brightness_upper"],
        ),
    ],
)
async def test_light_trigger_ignores_limit_entity_with_wrong_unit(
    hass: HomeAssistant,
    trigger: str,
    trigger_options: dict[str, Any],
    limit_entities: list[str],
) -> None:
    """Test numerical triggers do not fire if limit entities have the wrong unit."""
    await assert_trigger_ignores_limit_entities_with_wrong_unit(
        hass,
        trigger=trigger,
        trigger_options=trigger_options,
        entity_id="light.test_light",
        reset_state={"state": STATE_ON, "attributes": {ATTR_BRIGHTNESS: 0}},
        trigger_state={"state": STATE_ON, "attributes": {ATTR_BRIGHTNESS: 128}},
        limit_entities=[
            (limit_entities[0], "10"),
            (limit_entities[1], "90"),
        ],
        correct_unit="%",
        wrong_unit="lx",
    )
