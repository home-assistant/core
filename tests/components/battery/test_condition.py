"""Test battery conditions."""

from typing import Any

import pytest

from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    CONF_ABOVE,
    CONF_BELOW,
    CONF_CONDITION,
    CONF_ENTITY_ID,
    CONF_OPTIONS,
    CONF_TARGET,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.condition import (
    async_from_config as async_condition_from_config,
)

from tests.components import (
    ConditionStateDescription,
    assert_condition_gated_by_labs_flag,
    create_target_condition,
    parametrize_condition_states_all,
    parametrize_condition_states_any,
    parametrize_target_entities,
    set_or_remove_state,
    target_entities,
)


@pytest.fixture
async def target_binary_sensors(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple binary sensor entities associated with different targets."""
    return await target_entities(hass, "binary_sensor")


@pytest.fixture
async def target_sensors(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple sensor entities associated with different targets."""
    return await target_entities(hass, "sensor")


@pytest.fixture
async def target_numbers(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple number entities associated with different targets."""
    return await target_entities(hass, "number")


@pytest.mark.parametrize(
    "condition",
    [
        "battery.is_low",
        "battery.is_high",
        "battery.is_charging",
        "battery.is_not_charging",
        "battery.percentage",
    ],
)
async def test_battery_conditions_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, condition: str
) -> None:
    """Test the battery conditions are gated by the labs flag."""
    await assert_condition_gated_by_labs_flag(hass, caplog, condition)


# --- is_low / is_high (binary_sensor with device_class battery) ---


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("binary_sensor"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_any(
            condition="battery.is_low",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            additional_attributes={ATTR_DEVICE_CLASS: "battery"},
        ),
        *parametrize_condition_states_any(
            condition="battery.is_high",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            additional_attributes={ATTR_DEVICE_CLASS: "battery"},
        ),
    ],
)
async def test_battery_low_high_condition_behavior_any(
    hass: HomeAssistant,
    target_binary_sensors: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the battery is_low/is_high conditions with 'any' behavior."""
    other_entity_ids = set(target_binary_sensors["included"]) - {entity_id}

    for eid in target_binary_sensors["included"]:
        set_or_remove_state(hass, eid, states[0]["included"])
        await hass.async_block_till_done()

    condition = await create_target_condition(
        hass,
        condition=condition,
        target=condition_target_config,
        behavior="any",
    )

    for state in states:
        included_state = state["included"]
        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert condition(hass) == state["condition_true"]

        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert condition(hass) == state["condition_true"]


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("binary_sensor"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_all(
            condition="battery.is_low",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            additional_attributes={ATTR_DEVICE_CLASS: "battery"},
        ),
        *parametrize_condition_states_all(
            condition="battery.is_high",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            additional_attributes={ATTR_DEVICE_CLASS: "battery"},
        ),
    ],
)
async def test_battery_low_high_condition_behavior_all(
    hass: HomeAssistant,
    target_binary_sensors: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the battery is_low/is_high conditions with 'all' behavior."""
    other_entity_ids = set(target_binary_sensors["included"]) - {entity_id}

    for eid in target_binary_sensors["included"]:
        set_or_remove_state(hass, eid, states[0]["included"])
        await hass.async_block_till_done()

    condition = await create_target_condition(
        hass,
        condition=condition,
        target=condition_target_config,
        behavior="all",
    )

    for state in states:
        included_state = state["included"]

        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert condition(hass) == state["condition_true_first_entity"]

        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()

        assert condition(hass) == state["condition_true"]


# --- is_charging / is_not_charging (binary_sensor with device_class battery_charging) ---


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("binary_sensor"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_any(
            condition="battery.is_charging",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            additional_attributes={ATTR_DEVICE_CLASS: "battery_charging"},
        ),
        *parametrize_condition_states_any(
            condition="battery.is_not_charging",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            additional_attributes={ATTR_DEVICE_CLASS: "battery_charging"},
        ),
    ],
)
async def test_battery_charging_condition_behavior_any(
    hass: HomeAssistant,
    target_binary_sensors: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the battery is_charging/is_not_charging conditions with 'any' behavior."""
    other_entity_ids = set(target_binary_sensors["included"]) - {entity_id}

    for eid in target_binary_sensors["included"]:
        set_or_remove_state(hass, eid, states[0]["included"])
        await hass.async_block_till_done()

    condition = await create_target_condition(
        hass,
        condition=condition,
        target=condition_target_config,
        behavior="any",
    )

    for state in states:
        included_state = state["included"]
        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert condition(hass) == state["condition_true"]

        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert condition(hass) == state["condition_true"]


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("binary_sensor"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_all(
            condition="battery.is_charging",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            additional_attributes={ATTR_DEVICE_CLASS: "battery_charging"},
        ),
        *parametrize_condition_states_all(
            condition="battery.is_not_charging",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            additional_attributes={ATTR_DEVICE_CLASS: "battery_charging"},
        ),
    ],
)
async def test_battery_charging_condition_behavior_all(
    hass: HomeAssistant,
    target_binary_sensors: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the battery is_charging/is_not_charging conditions with 'all' behavior."""
    other_entity_ids = set(target_binary_sensors["included"]) - {entity_id}

    for eid in target_binary_sensors["included"]:
        set_or_remove_state(hass, eid, states[0]["included"])
        await hass.async_block_till_done()

    condition = await create_target_condition(
        hass,
        condition=condition,
        target=condition_target_config,
        behavior="all",
    )

    for state in states:
        included_state = state["included"]

        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert condition(hass) == state["condition_true_first_entity"]

        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()

        assert condition(hass) == state["condition_true"]


# --- Device class exclusion ---


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_key", "target_state", "other_state", "device_class"),
    [
        ("battery.is_low", STATE_ON, STATE_OFF, "battery"),
        ("battery.is_high", STATE_OFF, STATE_ON, "battery"),
        ("battery.is_charging", STATE_ON, STATE_OFF, "battery_charging"),
        ("battery.is_not_charging", STATE_OFF, STATE_ON, "battery_charging"),
    ],
)
async def test_battery_condition_excludes_wrong_device_class(
    hass: HomeAssistant,
    condition_key: str,
    target_state: str,
    other_state: str,
    device_class: str,
) -> None:
    """Test battery conditions do not match entities with wrong device class."""
    entity_correct = "binary_sensor.test_correct"
    entity_wrong = "binary_sensor.test_wrong"

    # Set initial states
    hass.states.async_set(
        entity_correct, other_state, {ATTR_DEVICE_CLASS: device_class}
    )
    hass.states.async_set(entity_wrong, other_state, {ATTR_DEVICE_CLASS: "door"})
    await hass.async_block_till_done()

    condition = await create_target_condition(
        hass,
        condition=condition_key,
        target={CONF_ENTITY_ID: [entity_correct, entity_wrong]},
        behavior="any",
    )

    # Neither matches yet
    assert condition(hass) is False

    # Wrong device class changes to target state - should NOT match
    hass.states.async_set(entity_wrong, target_state, {ATTR_DEVICE_CLASS: "door"})
    await hass.async_block_till_done()
    assert condition(hass) is False

    # Correct device class changes to target state - should match
    hass.states.async_set(
        entity_correct, target_state, {ATTR_DEVICE_CLASS: device_class}
    )
    await hass.async_block_till_done()
    assert condition(hass) is True


# --- percentage (sensor and number with device_class battery) ---


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("above", "below", "true_values", "false_values"),
    [
        (20, None, ["21", "50", "100"], ["0", "10", "20"]),
        (None, 80, ["0", "50", "79"], ["80", "90", "100"]),
        (20, 80, ["21", "50", "79"], ["0", "20", "80", "100"]),
    ],
)
@pytest.mark.parametrize("domain", ["sensor", "number"])
async def test_battery_percentage_condition(
    hass: HomeAssistant,
    above: float | None,
    below: float | None,
    true_values: list[str],
    false_values: list[str],
    domain: str,
) -> None:
    """Test the battery percentage condition with above/below thresholds."""
    entity_id = f"{domain}.test_battery"

    hass.states.async_set(entity_id, "50", {ATTR_DEVICE_CLASS: "battery"})
    await hass.async_block_till_done()

    options: dict[str, Any] = {"behavior": "any"}
    if above is not None:
        options[CONF_ABOVE] = above
    if below is not None:
        options[CONF_BELOW] = below

    condition = await async_condition_from_config(
        hass,
        {
            CONF_CONDITION: "battery.percentage",
            CONF_TARGET: {CONF_ENTITY_ID: [entity_id]},
            CONF_OPTIONS: options,
        },
    )

    for value in true_values:
        hass.states.async_set(entity_id, value, {ATTR_DEVICE_CLASS: "battery"})
        await hass.async_block_till_done()
        assert condition(hass) is True, f"Expected True for {value}"

    for value in false_values:
        hass.states.async_set(entity_id, value, {ATTR_DEVICE_CLASS: "battery"})
        await hass.async_block_till_done()
        assert condition(hass) is False, f"Expected False for {value}"


@pytest.mark.usefixtures("enable_labs_preview_features")
async def test_battery_percentage_condition_invalid_state(
    hass: HomeAssistant,
) -> None:
    """Test the battery percentage condition with non-numeric states."""
    entity_id = "sensor.test_battery"

    hass.states.async_set(entity_id, "50", {ATTR_DEVICE_CLASS: "battery"})
    await hass.async_block_till_done()

    condition = await async_condition_from_config(
        hass,
        {
            CONF_CONDITION: "battery.percentage",
            CONF_TARGET: {CONF_ENTITY_ID: [entity_id]},
            CONF_OPTIONS: {"behavior": "any", CONF_ABOVE: 20},
        },
    )

    for value in ("unavailable", "unknown", "abc"):
        hass.states.async_set(entity_id, value, {ATTR_DEVICE_CLASS: "battery"})
        await hass.async_block_till_done()
        assert condition(hass) is False, f"Expected False for '{value}'"


@pytest.mark.usefixtures("enable_labs_preview_features")
async def test_battery_percentage_condition_excludes_wrong_device_class(
    hass: HomeAssistant,
) -> None:
    """Test battery percentage condition excludes entities with wrong device class."""
    entity_battery = "sensor.test_battery"
    entity_temperature = "sensor.test_temperature"

    hass.states.async_set(entity_battery, "10", {ATTR_DEVICE_CLASS: "battery"})
    hass.states.async_set(entity_temperature, "10", {ATTR_DEVICE_CLASS: "temperature"})
    await hass.async_block_till_done()

    condition = await async_condition_from_config(
        hass,
        {
            CONF_CONDITION: "battery.percentage",
            CONF_TARGET: {
                CONF_ENTITY_ID: [entity_battery, entity_temperature],
            },
            CONF_OPTIONS: {"behavior": "any", CONF_ABOVE: 50},
        },
    )

    # Both below threshold
    assert condition(hass) is False

    # Only temperature entity goes above threshold - should NOT match
    hass.states.async_set(entity_temperature, "90", {ATTR_DEVICE_CLASS: "temperature"})
    await hass.async_block_till_done()
    assert condition(hass) is False

    # Battery entity goes above threshold - should match
    hass.states.async_set(entity_battery, "90", {ATTR_DEVICE_CLASS: "battery"})
    await hass.async_block_till_done()
    assert condition(hass) is True
