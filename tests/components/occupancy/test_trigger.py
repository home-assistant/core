"""Test occupancy trigger."""

from typing import Any

import pytest

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import ATTR_DEVICE_CLASS, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, ServiceCall

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
async def target_binary_sensors(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple binary sensor entities associated with different targets."""
    return await target_entities(hass, "binary_sensor")


@pytest.mark.parametrize(
    "trigger_key",
    [
        "occupancy.detected",
        "occupancy.cleared",
    ],
)
async def test_occupancy_triggers_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, trigger_key: str
) -> None:
    """Test the occupancy triggers are gated by the labs flag."""
    await assert_trigger_gated_by_labs_flag(hass, caplog, trigger_key)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("binary_sensor"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="occupancy.detected",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            required_filter_attributes={
                ATTR_DEVICE_CLASS: BinarySensorDeviceClass.OCCUPANCY
            },
            trigger_from_none=False,
        ),
        *parametrize_trigger_states(
            trigger="occupancy.cleared",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            required_filter_attributes={
                ATTR_DEVICE_CLASS: BinarySensorDeviceClass.OCCUPANCY
            },
            trigger_from_none=False,
        ),
    ],
)
async def test_occupancy_trigger_binary_sensor_behavior_any(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_binary_sensors: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test occupancy trigger fires for binary_sensor entities with device_class occupancy."""
    await assert_trigger_behavior_any(
        hass,
        service_calls=service_calls,
        target_entities=target_binary_sensors,
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
    parametrize_target_entities("binary_sensor"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="occupancy.detected",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            required_filter_attributes={
                ATTR_DEVICE_CLASS: BinarySensorDeviceClass.OCCUPANCY
            },
            trigger_from_none=False,
        ),
        *parametrize_trigger_states(
            trigger="occupancy.cleared",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            required_filter_attributes={
                ATTR_DEVICE_CLASS: BinarySensorDeviceClass.OCCUPANCY
            },
            trigger_from_none=False,
        ),
    ],
)
async def test_occupancy_trigger_binary_sensor_behavior_first(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_binary_sensors: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test occupancy trigger fires on the first binary_sensor state change."""
    await assert_trigger_behavior_first(
        hass,
        service_calls=service_calls,
        target_entities=target_binary_sensors,
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
    parametrize_target_entities("binary_sensor"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="occupancy.detected",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            required_filter_attributes={
                ATTR_DEVICE_CLASS: BinarySensorDeviceClass.OCCUPANCY
            },
            trigger_from_none=False,
        ),
        *parametrize_trigger_states(
            trigger="occupancy.cleared",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            required_filter_attributes={
                ATTR_DEVICE_CLASS: BinarySensorDeviceClass.OCCUPANCY
            },
            trigger_from_none=False,
        ),
    ],
)
async def test_occupancy_trigger_binary_sensor_behavior_last(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_binary_sensors: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test occupancy trigger fires when the last binary_sensor changes state."""
    await assert_trigger_behavior_last(
        hass,
        service_calls=service_calls,
        target_entities=target_binary_sensors,
        trigger_target_config=trigger_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        trigger=trigger,
        trigger_options=trigger_options,
        states=states,
    )
