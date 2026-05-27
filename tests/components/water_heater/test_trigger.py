"""Test water heater trigger."""

from typing import Any

import pytest

from homeassistant.components.water_heater import (
    STATE_ECO,
    STATE_ELECTRIC,
    STATE_GAS,
    STATE_HEAT_PUMP,
    STATE_HIGH_DEMAND,
    STATE_PERFORMANCE,
)
from homeassistant.const import ATTR_TEMPERATURE, STATE_OFF, STATE_ON, UnitOfTemperature
from homeassistant.core import HomeAssistant

from tests.components.common import (
    TriggerStateDescription,
    assert_trigger_behavior_all,
    assert_trigger_behavior_each,
    assert_trigger_behavior_first,
    assert_trigger_gated_by_labs_flag,
    assert_trigger_options_supported,
    parametrize_numerical_attribute_changed_trigger_states,
    parametrize_numerical_attribute_crossed_threshold_trigger_states,
    parametrize_target_entities,
    parametrize_trigger_states,
    target_entities,
)

ALL_ON_STATES = [
    STATE_ECO,
    STATE_ELECTRIC,
    STATE_GAS,
    STATE_HEAT_PUMP,
    STATE_HIGH_DEMAND,
    STATE_ON,
    STATE_PERFORMANCE,
]

ALL_STATES = [STATE_OFF, *ALL_ON_STATES]


@pytest.fixture
async def target_water_heaters(hass: HomeAssistant) -> list[str]:
    """Create multiple water heater entities associated with different targets."""
    return await target_entities(hass, "water_heater")


@pytest.mark.parametrize(
    "trigger_key",
    [
        "water_heater.operation_mode_changed",
        "water_heater.target_temperature_changed",
        "water_heater.target_temperature_crossed_threshold",
        "water_heater.turned_off",
        "water_heater.turned_on",
    ],
)
async def test_water_heater_triggers_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, trigger_key: str
) -> None:
    """Test the water heater triggers are gated by the labs flag."""
    await assert_trigger_gated_by_labs_flag(hass, caplog, trigger_key)


_CHANGED_THRESHOLD = {"threshold": {"type": "any"}}
_CROSSED_THRESHOLD = {
    "threshold": {
        "type": "above",
        "value": {"number": 20, "unit_of_measurement": UnitOfTemperature.CELSIUS},
    }
}


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_key", "base_options", "supports_behavior", "supports_duration"),
    [
        ("water_heater.turned_off", {}, True, True),
        ("water_heater.turned_on", {}, True, True),
        (
            "water_heater.operation_mode_changed",
            {"operation_mode": [STATE_ECO]},
            True,
            True,
        ),
        (
            "water_heater.target_temperature_changed",
            _CHANGED_THRESHOLD,
            False,
            False,
        ),
        (
            "water_heater.target_temperature_crossed_threshold",
            _CROSSED_THRESHOLD,
            True,
            True,
        ),
    ],
)
async def test_water_heater_trigger_options_validation(
    hass: HomeAssistant,
    trigger_key: str,
    base_options: dict[str, Any] | None,
    supports_behavior: bool,
    supports_duration: bool,
) -> None:
    """Test that water_heater triggers support the expected options."""
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
    parametrize_target_entities("water_heater"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *(
            param
            for mode in ALL_STATES
            for param in parametrize_trigger_states(
                trigger="water_heater.operation_mode_changed",
                trigger_options={"operation_mode": [mode]},
                target_states=[mode],
                other_states=[s for s in ALL_STATES if s != mode],
            )
        ),
        *parametrize_trigger_states(
            trigger="water_heater.operation_mode_changed",
            trigger_options={"operation_mode": [STATE_ECO, STATE_ELECTRIC]},
            target_states=[STATE_ECO, STATE_ELECTRIC],
            other_states=[
                s for s in ALL_STATES if s not in (STATE_ECO, STATE_ELECTRIC)
            ],
        ),
        *parametrize_trigger_states(
            trigger="water_heater.turned_off",
            target_states=[STATE_OFF],
            other_states=ALL_ON_STATES,
        ),
        *parametrize_trigger_states(
            trigger="water_heater.turned_on",
            target_states=ALL_ON_STATES,
            other_states=[STATE_OFF],
        ),
    ],
)
async def test_water_heater_state_trigger_behavior_each(
    hass: HomeAssistant,
    target_water_heaters: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test water heater state trigger fires on any state change."""
    await assert_trigger_behavior_each(
        hass,
        target_entities=target_water_heaters,
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
    parametrize_target_entities("water_heater"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_numerical_attribute_changed_trigger_states(
            "water_heater.target_temperature_changed",
            STATE_ECO,
            ATTR_TEMPERATURE,
            threshold_unit=UnitOfTemperature.CELSIUS,
            attribute_required=True,
        ),
        *parametrize_numerical_attribute_crossed_threshold_trigger_states(
            "water_heater.target_temperature_crossed_threshold",
            STATE_ECO,
            ATTR_TEMPERATURE,
            threshold_unit=UnitOfTemperature.CELSIUS,
            attribute_required=True,
        ),
    ],
)
async def test_water_heater_state_attribute_trigger_behavior_each(
    hass: HomeAssistant,
    target_water_heaters: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test water heater target temp trigger fires on threshold cross."""
    await assert_trigger_behavior_each(
        hass,
        target_entities=target_water_heaters,
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
    parametrize_target_entities("water_heater"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *(
            param
            for mode in ALL_STATES
            for param in parametrize_trigger_states(
                trigger="water_heater.operation_mode_changed",
                trigger_options={"operation_mode": [mode]},
                target_states=[mode],
                other_states=[s for s in ALL_STATES if s != mode],
            )
        ),
        *parametrize_trigger_states(
            trigger="water_heater.operation_mode_changed",
            trigger_options={"operation_mode": [STATE_ECO, STATE_ELECTRIC]},
            target_states=[STATE_ECO, STATE_ELECTRIC],
            other_states=[
                s for s in ALL_STATES if s not in (STATE_ECO, STATE_ELECTRIC)
            ],
        ),
        *parametrize_trigger_states(
            trigger="water_heater.turned_off",
            target_states=[STATE_OFF],
            other_states=ALL_ON_STATES,
        ),
        *parametrize_trigger_states(
            trigger="water_heater.turned_on",
            target_states=ALL_ON_STATES,
            other_states=[STATE_OFF],
        ),
    ],
)
async def test_water_heater_state_trigger_behavior_first(
    hass: HomeAssistant,
    target_water_heaters: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test water heater state trigger fires on first entity change."""
    await assert_trigger_behavior_first(
        hass,
        target_entities=target_water_heaters,
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
    parametrize_target_entities("water_heater"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_numerical_attribute_crossed_threshold_trigger_states(
            "water_heater.target_temperature_crossed_threshold",
            STATE_ECO,
            ATTR_TEMPERATURE,
            threshold_unit=UnitOfTemperature.CELSIUS,
            attribute_required=True,
        ),
    ],
)
async def test_water_heater_state_attribute_trigger_behavior_first(
    hass: HomeAssistant,
    target_water_heaters: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[tuple[tuple[str, dict], int]],
) -> None:
    """Test water heater temp trigger fires on first entity threshold."""
    await assert_trigger_behavior_first(
        hass,
        target_entities=target_water_heaters,
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
    parametrize_target_entities("water_heater"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *(
            param
            for mode in ALL_STATES
            for param in parametrize_trigger_states(
                trigger="water_heater.operation_mode_changed",
                trigger_options={"operation_mode": [mode]},
                target_states=[mode],
                other_states=[s for s in ALL_STATES if s != mode],
            )
        ),
        *parametrize_trigger_states(
            trigger="water_heater.operation_mode_changed",
            trigger_options={"operation_mode": [STATE_ECO, STATE_ELECTRIC]},
            target_states=[STATE_ECO, STATE_ELECTRIC],
            other_states=[
                s for s in ALL_STATES if s not in (STATE_ECO, STATE_ELECTRIC)
            ],
        ),
        *parametrize_trigger_states(
            trigger="water_heater.turned_off",
            target_states=[STATE_OFF],
            other_states=ALL_ON_STATES,
        ),
        *parametrize_trigger_states(
            trigger="water_heater.turned_on",
            target_states=ALL_ON_STATES,
            other_states=[STATE_OFF],
        ),
    ],
)
async def test_water_heater_state_trigger_behavior_all(
    hass: HomeAssistant,
    target_water_heaters: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test water heater state trigger fires when all entities have changed."""
    await assert_trigger_behavior_all(
        hass,
        target_entities=target_water_heaters,
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
    parametrize_target_entities("water_heater"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_numerical_attribute_crossed_threshold_trigger_states(
            "water_heater.target_temperature_crossed_threshold",
            STATE_ECO,
            ATTR_TEMPERATURE,
            threshold_unit=UnitOfTemperature.CELSIUS,
            attribute_required=True,
        ),
    ],
)
async def test_water_heater_state_attribute_trigger_behavior_all(
    hass: HomeAssistant,
    target_water_heaters: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[tuple[tuple[str, dict], int]],
) -> None:
    """Test water heater temp trigger fires when all entities have crossed threshold."""
    await assert_trigger_behavior_all(
        hass,
        target_entities=target_water_heaters,
        trigger_target_config=trigger_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        trigger=trigger,
        trigger_options=trigger_options,
        states=states,
    )
