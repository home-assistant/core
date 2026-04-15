"""Test window conditions."""

from typing import Any

import pytest

from homeassistant.components.cover import ATTR_IS_CLOSED, CoverState
from homeassistant.const import ATTR_DEVICE_CLASS, CONF_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from tests.components.common import (
    ConditionStateDescription,
    assert_condition_behavior_all,
    assert_condition_behavior_any,
    assert_condition_gated_by_labs_flag,
    create_target_condition,
    parametrize_condition_states_all,
    parametrize_condition_states_any,
    parametrize_target_entities,
    target_entities,
)


@pytest.fixture
async def target_binary_sensors(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple binary sensor entities associated with different targets."""
    return await target_entities(hass, "binary_sensor")


@pytest.fixture
async def target_covers(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple cover entities associated with different targets."""
    return await target_entities(hass, "cover")


@pytest.mark.parametrize(
    "condition",
    [
        "window.is_closed",
        "window.is_open",
    ],
)
async def test_window_conditions_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, condition: str
) -> None:
    """Test the window conditions are gated by the labs flag."""
    await assert_condition_gated_by_labs_flag(hass, caplog, condition)


# --- binary_sensor tests ---


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("binary_sensor"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_any(
            condition="window.is_open",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            required_filter_attributes={ATTR_DEVICE_CLASS: "window"},
        ),
        *parametrize_condition_states_any(
            condition="window.is_closed",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            required_filter_attributes={ATTR_DEVICE_CLASS: "window"},
        ),
    ],
)
async def test_window_binary_sensor_condition_behavior_any(
    hass: HomeAssistant,
    target_binary_sensors: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test window condition for binary_sensor with 'any' behavior."""
    await assert_condition_behavior_any(
        hass,
        target_entities=target_binary_sensors,
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
    parametrize_target_entities("binary_sensor"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_all(
            condition="window.is_open",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            required_filter_attributes={ATTR_DEVICE_CLASS: "window"},
        ),
        *parametrize_condition_states_all(
            condition="window.is_closed",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            required_filter_attributes={ATTR_DEVICE_CLASS: "window"},
        ),
    ],
)
async def test_window_binary_sensor_condition_behavior_all(
    hass: HomeAssistant,
    target_binary_sensors: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test window condition for binary_sensor with 'all' behavior."""
    await assert_condition_behavior_all(
        hass,
        target_entities=target_binary_sensors,
        condition_target_config=condition_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        condition=condition,
        condition_options=condition_options,
        states=states,
    )


# --- cover tests ---


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("cover"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_any(
            condition="window.is_open",
            target_states=[
                (CoverState.OPEN, {ATTR_IS_CLOSED: False}),
                (CoverState.OPENING, {ATTR_IS_CLOSED: False}),
                (CoverState.CLOSING, {ATTR_IS_CLOSED: False}),
            ],
            other_states=[
                (CoverState.CLOSED, {ATTR_IS_CLOSED: True}),
                (CoverState.CLOSING, {ATTR_IS_CLOSED: True}),
            ],
            required_filter_attributes={ATTR_DEVICE_CLASS: "window"},
        ),
        *parametrize_condition_states_any(
            condition="window.is_closed",
            target_states=[
                (CoverState.CLOSED, {ATTR_IS_CLOSED: True}),
                (CoverState.CLOSING, {ATTR_IS_CLOSED: True}),
            ],
            other_states=[
                (CoverState.OPEN, {ATTR_IS_CLOSED: False}),
                (CoverState.OPENING, {ATTR_IS_CLOSED: False}),
                (CoverState.CLOSING, {ATTR_IS_CLOSED: False}),
            ],
            required_filter_attributes={ATTR_DEVICE_CLASS: "window"},
        ),
    ],
)
async def test_window_cover_condition_behavior_any(
    hass: HomeAssistant,
    target_covers: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test window condition for cover entities with 'any' behavior."""
    await assert_condition_behavior_any(
        hass,
        target_entities=target_covers,
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
    parametrize_target_entities("cover"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_all(
            condition="window.is_open",
            target_states=[
                (CoverState.OPEN, {ATTR_IS_CLOSED: False}),
                (CoverState.OPENING, {ATTR_IS_CLOSED: False}),
                (CoverState.CLOSING, {ATTR_IS_CLOSED: False}),
            ],
            other_states=[
                (CoverState.CLOSED, {ATTR_IS_CLOSED: True}),
                (CoverState.CLOSING, {ATTR_IS_CLOSED: True}),
            ],
            required_filter_attributes={ATTR_DEVICE_CLASS: "window"},
        ),
        *parametrize_condition_states_all(
            condition="window.is_closed",
            target_states=[
                (CoverState.CLOSED, {ATTR_IS_CLOSED: True}),
                (CoverState.CLOSING, {ATTR_IS_CLOSED: True}),
            ],
            other_states=[
                (CoverState.OPEN, {ATTR_IS_CLOSED: False}),
                (CoverState.OPENING, {ATTR_IS_CLOSED: False}),
                (CoverState.CLOSING, {ATTR_IS_CLOSED: False}),
            ],
            required_filter_attributes={ATTR_DEVICE_CLASS: "window"},
        ),
    ],
)
async def test_window_cover_condition_behavior_all(
    hass: HomeAssistant,
    target_covers: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test window condition for cover entities with 'all' behavior."""
    await assert_condition_behavior_all(
        hass,
        target_entities=target_covers,
        condition_target_config=condition_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        condition=condition,
        condition_options=condition_options,
        states=states,
    )


# --- Cross-domain device class exclusion test ---


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    (
        "condition_key",
        "binary_sensor_matching",
        "binary_sensor_non_matching",
        "cover_matching",
        "cover_matching_is_closed",
        "cover_non_matching",
        "cover_non_matching_is_closed",
    ),
    [
        (
            "window.is_open",
            STATE_ON,
            STATE_OFF,
            CoverState.OPEN,
            False,
            CoverState.CLOSED,
            True,
        ),
        (
            "window.is_closed",
            STATE_OFF,
            STATE_ON,
            CoverState.CLOSED,
            True,
            CoverState.OPEN,
            False,
        ),
    ],
)
async def test_window_condition_excludes_non_window_device_class(
    hass: HomeAssistant,
    condition_key: str,
    binary_sensor_matching: str,
    binary_sensor_non_matching: str,
    cover_matching: str,
    cover_matching_is_closed: bool,
    cover_non_matching: str,
    cover_non_matching_is_closed: bool,
) -> None:
    """Test window condition excludes entities without device_class window."""
    entity_id_window = "binary_sensor.test_window"
    entity_id_door = "binary_sensor.test_door"
    entity_id_cover_window = "cover.test_window"
    entity_id_cover_garage = "cover.test_garage"

    all_entities = [
        entity_id_window,
        entity_id_door,
        entity_id_cover_window,
        entity_id_cover_garage,
    ]

    # Set matching states on all entities
    hass.states.async_set(
        entity_id_window, binary_sensor_matching, {ATTR_DEVICE_CLASS: "window"}
    )
    hass.states.async_set(
        entity_id_door, binary_sensor_matching, {ATTR_DEVICE_CLASS: "door"}
    )
    hass.states.async_set(
        entity_id_cover_window,
        cover_matching,
        {ATTR_DEVICE_CLASS: "window", ATTR_IS_CLOSED: cover_matching_is_closed},
    )
    hass.states.async_set(
        entity_id_cover_garage,
        cover_matching,
        {ATTR_DEVICE_CLASS: "garage", ATTR_IS_CLOSED: cover_matching_is_closed},
    )
    await hass.async_block_till_done()

    condition_any = await create_target_condition(
        hass,
        condition=condition_key,
        target={CONF_ENTITY_ID: all_entities},
        behavior="any",
    )

    # Matching entities in matching state - condition should be True
    assert condition_any(hass) is True

    # Set matching entities to non-matching state
    hass.states.async_set(
        entity_id_window, binary_sensor_non_matching, {ATTR_DEVICE_CLASS: "window"}
    )
    hass.states.async_set(
        entity_id_cover_window,
        cover_non_matching,
        {ATTR_DEVICE_CLASS: "window", ATTR_IS_CLOSED: cover_non_matching_is_closed},
    )
    await hass.async_block_till_done()

    # Wrong device class entities still in matching state, but should be excluded
    assert condition_any(hass) is False
