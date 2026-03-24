"""Test light trigger."""

from typing import Any

import pytest

from homeassistant.components.light import ATTR_BRIGHTNESS
from homeassistant.const import CONF_ABOVE, CONF_BELOW, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.trigger import (
    CONF_LOWER_LIMIT,
    CONF_THRESHOLD_TYPE,
    CONF_UPPER_LIMIT,
    ThresholdType,
)

from tests.components.common import (
    TriggerStateDescription,
    assert_trigger_behavior_any,
    assert_trigger_behavior_first,
    assert_trigger_behavior_last,
    assert_trigger_gated_by_labs_flag,
    assert_trigger_ignores_limit_entities_with_wrong_unit,
    parametrize_target_entities,
    parametrize_trigger_states,
    target_entities,
)


@pytest.fixture
async def target_lights(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple light entities associated with different targets."""
    return await target_entities(hass, "light")


def parametrize_brightness_changed_trigger_states(
    trigger: str, state: str, attribute: str
) -> list[tuple[str, dict[str, Any], list[TriggerStateDescription]]]:
    """Parametrize states and expected service call counts for brightness changed triggers.

    Note: The brightness in the trigger configuration is in percentage (0-100) scale,
    the underlying attribute in the state is in uint8 (0-255) scale.
    """
    return [
        *parametrize_trigger_states(
            trigger=trigger,
            trigger_options={},
            target_states=[
                (state, {attribute: 0}),
                (state, {attribute: 128}),
                (state, {attribute: 255}),
            ],
            other_states=[(state, {attribute: None})],
            retrigger_on_target_state=True,
        ),
        *parametrize_trigger_states(
            trigger=trigger,
            trigger_options={CONF_ABOVE: 10},
            target_states=[
                (state, {attribute: 128}),
                (state, {attribute: 255}),
            ],
            other_states=[
                (state, {attribute: None}),
                (state, {attribute: 0}),
            ],
            retrigger_on_target_state=True,
        ),
        *parametrize_trigger_states(
            trigger=trigger,
            trigger_options={CONF_BELOW: 90},
            target_states=[
                (state, {attribute: 0}),
                (state, {attribute: 128}),
            ],
            other_states=[
                (state, {attribute: None}),
                (state, {attribute: 255}),
            ],
            retrigger_on_target_state=True,
        ),
    ]


def parametrize_brightness_crossed_threshold_trigger_states(
    trigger: str, state: str, attribute: str
) -> list[tuple[str, dict[str, Any], list[TriggerStateDescription]]]:
    """Parametrize states and expected service call counts for brightness crossed threshold triggers.

    Note: The brightness in the trigger configuration is in percentage (0-100) scale,
    the underlying attribute in the state is in uint8 (0-255) scale.
    """
    return [
        *parametrize_trigger_states(
            trigger=trigger,
            trigger_options={
                CONF_THRESHOLD_TYPE: ThresholdType.BETWEEN,
                CONF_LOWER_LIMIT: 10,
                CONF_UPPER_LIMIT: 90,
            },
            target_states=[
                (state, {attribute: 128}),
                (state, {attribute: 153}),
            ],
            other_states=[
                (state, {attribute: None}),
                (state, {attribute: 0}),
                (state, {attribute: 255}),
            ],
        ),
        *parametrize_trigger_states(
            trigger=trigger,
            trigger_options={
                CONF_THRESHOLD_TYPE: ThresholdType.OUTSIDE,
                CONF_LOWER_LIMIT: 10,
                CONF_UPPER_LIMIT: 90,
            },
            target_states=[
                (state, {attribute: 0}),
                (state, {attribute: 255}),
            ],
            other_states=[
                (state, {attribute: None}),
                (state, {attribute: 128}),
                (state, {attribute: 153}),
            ],
        ),
        *parametrize_trigger_states(
            trigger=trigger,
            trigger_options={
                CONF_THRESHOLD_TYPE: ThresholdType.ABOVE,
                CONF_LOWER_LIMIT: 10,
            },
            target_states=[
                (state, {attribute: 128}),
                (state, {attribute: 255}),
            ],
            other_states=[
                (state, {attribute: None}),
                (state, {attribute: 0}),
            ],
        ),
        *parametrize_trigger_states(
            trigger=trigger,
            trigger_options={
                CONF_THRESHOLD_TYPE: ThresholdType.BELOW,
                CONF_UPPER_LIMIT: 90,
            },
            target_states=[
                (state, {attribute: 0}),
                (state, {attribute: 128}),
            ],
            other_states=[
                (state, {attribute: None}),
                (state, {attribute: 255}),
            ],
        ),
    ]


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
async def test_light_state_trigger_behavior_any(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_lights: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the light state trigger fires when any light state changes to a specific state."""
    await assert_trigger_behavior_any(
        hass,
        service_calls=service_calls,
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
        *parametrize_brightness_changed_trigger_states(
            "light.brightness_changed", STATE_ON, ATTR_BRIGHTNESS
        ),
        *parametrize_brightness_crossed_threshold_trigger_states(
            "light.brightness_crossed_threshold", STATE_ON, ATTR_BRIGHTNESS
        ),
    ],
)
async def test_light_state_attribute_trigger_behavior_any(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_lights: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the light state trigger fires when any light state changes to a specific state."""
    await assert_trigger_behavior_any(
        hass,
        service_calls=service_calls,
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
    service_calls: list[ServiceCall],
    target_lights: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the light state trigger fires when the first light changes to a specific state."""
    await assert_trigger_behavior_first(
        hass,
        service_calls=service_calls,
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
        *parametrize_brightness_crossed_threshold_trigger_states(
            "light.brightness_crossed_threshold", STATE_ON, ATTR_BRIGHTNESS
        ),
    ],
)
async def test_light_state_attribute_trigger_behavior_first(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_lights: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[tuple[tuple[str, dict], int]],
) -> None:
    """Test that the light state trigger fires when the first light state changes to a specific state."""
    await assert_trigger_behavior_first(
        hass,
        service_calls=service_calls,
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
async def test_light_state_trigger_behavior_last(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_lights: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the light state trigger fires when the last light changes to a specific state."""
    await assert_trigger_behavior_last(
        hass,
        service_calls=service_calls,
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
        *parametrize_brightness_crossed_threshold_trigger_states(
            "light.brightness_crossed_threshold", STATE_ON, ATTR_BRIGHTNESS
        ),
    ],
)
async def test_light_state_attribute_trigger_behavior_last(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_lights: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[tuple[tuple[str, dict], int]],
) -> None:
    """Test that the light state trigger fires when the last light state changes to a specific state."""
    await assert_trigger_behavior_last(
        hass,
        service_calls=service_calls,
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
                CONF_ABOVE: "sensor.brightness_above",
                CONF_BELOW: "sensor.brightness_below",
            },
            ["sensor.brightness_above", "sensor.brightness_below"],
        ),
        (
            "light.brightness_crossed_threshold",
            {
                CONF_THRESHOLD_TYPE: ThresholdType.BETWEEN,
                CONF_LOWER_LIMIT: "sensor.brightness_lower",
                CONF_UPPER_LIMIT: "sensor.brightness_upper",
            },
            ["sensor.brightness_lower", "sensor.brightness_upper"],
        ),
    ],
)
async def test_light_trigger_ignores_limit_entity_with_wrong_unit(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    trigger: str,
    trigger_options: dict[str, Any],
    limit_entities: list[str],
) -> None:
    """Test numerical triggers do not fire if limit entities have the wrong unit."""
    await assert_trigger_ignores_limit_entities_with_wrong_unit(
        hass,
        service_calls=service_calls,
        trigger=trigger,
        trigger_options=trigger_options,
        entity_id="light.test_light",
        entity_state=STATE_ON,
        reset_attributes={ATTR_BRIGHTNESS: 0},
        trigger_attributes={ATTR_BRIGHTNESS: 128},
        limit_entities=[
            (limit_entities[0], "10"),
            (limit_entities[1], "90"),
        ],
        correct_unit="%",
        wrong_unit="lx",
    )
