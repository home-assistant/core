"""Test ESPHome climates."""

import math
from unittest.mock import call

from aioesphomeapi import (
    APIClient,
    ClimateAction,
    ClimateFanMode,
    ClimateFeature,
    ClimateInfo,
    ClimateMode,
    ClimatePreset,
    ClimateState,
    ClimateSwingMode,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_CURRENT_HUMIDITY,
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_HUMIDITY,
    ATTR_HVAC_MODE,
    ATTR_MAX_HUMIDITY,
    ATTR_MIN_HUMIDITY,
    ATTR_PRESET_MODE,
    ATTR_SWING_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ATTR_TEMPERATURE,
    DOMAIN as CLIMATE_DOMAIN,
    FAN_HIGH,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HUMIDITY,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
    SWING_BOTH,
    HVACMode,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from .conftest import MockGenericDeviceEntryType


async def test_climate_entity(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test a generic climate entity."""
    entity_info = [
        ClimateInfo(
            object_id="myclimate",
            key=1,
            name="my climate",
            supports_current_temperature=True,
            supports_action=True,
            visual_min_temperature=10.0,
            visual_max_temperature=30.0,
        )
    ]
    states = [
        ClimateState(
            key=1,
            mode=ClimateMode.COOL,
            action=ClimateAction.COOLING,
            current_temperature=30,
            target_temperature=20,
            fan_mode=ClimateFanMode.AUTO,
            swing_mode=ClimateSwingMode.BOTH,
        )
    ]
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        states=states,
    )
    state = hass.states.get("climate.test_my_climate")
    assert state is not None
    assert state.state == HVACMode.COOL

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: "climate.test_my_climate", ATTR_TEMPERATURE: 25},
        blocking=True,
    )
    mock_client.climate_command.assert_has_calls(
        [call(key=1, target_temperature=25.0, device_id=0)]
    )
    mock_client.climate_command.reset_mock()


async def test_climate_entity_with_step_and_two_point(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test a generic climate entity."""
    entity_info = [
        ClimateInfo(
            object_id="myclimate",
            key=1,
            name="my climate",
            feature_flags=ClimateFeature.SUPPORTS_CURRENT_TEMPERATURE
            | ClimateFeature.SUPPORTS_TWO_POINT_TARGET_TEMPERATURE,
            visual_target_temperature_step=2,
            visual_current_temperature_step=2,
            visual_min_temperature=10.0,
            visual_max_temperature=30.0,
            supported_modes=[ClimateMode.COOL, ClimateMode.HEAT, ClimateMode.AUTO],
            supported_presets=[ClimatePreset.AWAY, ClimatePreset.ACTIVITY],
        )
    ]
    states = [
        ClimateState(
            key=1,
            mode=ClimateMode.COOL,
            current_temperature=30,
            target_temperature=20,
            fan_mode=ClimateFanMode.AUTO,
            swing_mode=ClimateSwingMode.BOTH,
        )
    ]
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        states=states,
    )
    state = hass.states.get("climate.test_my_climate")
    assert state is not None
    assert state.state == HVACMode.COOL

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: "climate.test_my_climate", ATTR_TEMPERATURE: 25},
        blocking=True,
    )

    mock_client.climate_command.assert_has_calls(
        [
            call(
                key=1,
                target_temperature_high=25.0,
                device_id=0,
            )
        ]
    )
    mock_client.climate_command.reset_mock()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: "climate.test_my_climate",
            ATTR_HVAC_MODE: HVACMode.AUTO,
            ATTR_TARGET_TEMP_LOW: 20,
            ATTR_TARGET_TEMP_HIGH: 30,
        },
        blocking=True,
    )
    mock_client.climate_command.assert_has_calls(
        [
            call(
                key=1,
                mode=ClimateMode.AUTO,
                target_temperature_low=20.0,
                target_temperature_high=30.0,
                device_id=0,
            )
        ]
    )
    mock_client.climate_command.reset_mock()


async def test_climate_entity_with_step_and_target_temp(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test a generic climate entity."""
    entity_info = [
        ClimateInfo(
            object_id="myclimate",
            key=1,
            name="my climate",
            supports_current_temperature=True,
            visual_target_temperature_step=2,
            visual_current_temperature_step=2,
            supports_action=True,
            visual_min_temperature=10.0,
            visual_max_temperature=30.0,
            supported_fan_modes=[ClimateFanMode.LOW, ClimateFanMode.HIGH],
            supported_modes=[ClimateMode.COOL, ClimateMode.HEAT, ClimateMode.AUTO],
            supported_presets=[ClimatePreset.AWAY, ClimatePreset.ACTIVITY],
            supported_custom_presets=["preset1", "preset2"],
            supported_custom_fan_modes=["fan1", "fan2"],
            supported_swing_modes=[ClimateSwingMode.BOTH, ClimateSwingMode.OFF],
        )
    ]
    states = [
        ClimateState(
            key=1,
            mode=ClimateMode.COOL,
            action=ClimateAction.COOLING,
            current_temperature=30,
            target_temperature=20,
            fan_mode=ClimateFanMode.AUTO,
            swing_mode=ClimateSwingMode.BOTH,
        )
    ]
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        states=states,
    )
    state = hass.states.get("climate.test_my_climate")
    assert state is not None
    assert state.state == HVACMode.COOL

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: "climate.test_my_climate",
            ATTR_HVAC_MODE: HVACMode.AUTO,
            ATTR_TEMPERATURE: 25,
        },
        blocking=True,
    )
    mock_client.climate_command.assert_has_calls(
        [call(key=1, mode=ClimateMode.AUTO, target_temperature=25.0, device_id=0)]
    )
    mock_client.climate_command.reset_mock()

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: "climate.test_my_climate",
                ATTR_HVAC_MODE: HVACMode.AUTO,
                ATTR_TARGET_TEMP_LOW: 20,
                ATTR_TARGET_TEMP_HIGH: 30,
            },
            blocking=True,
        )

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {
            ATTR_ENTITY_ID: "climate.test_my_climate",
            ATTR_HVAC_MODE: HVACMode.HEAT,
        },
        blocking=True,
    )
    mock_client.climate_command.assert_has_calls(
        [
            call(
                key=1,
                mode=ClimateMode.HEAT,
                device_id=0,
            )
        ]
    )
    mock_client.climate_command.reset_mock()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: "climate.test_my_climate", ATTR_PRESET_MODE: "away"},
        blocking=True,
    )
    mock_client.climate_command.assert_has_calls(
        [
            call(
                key=1,
                preset=ClimatePreset.AWAY,
                device_id=0,
            )
        ]
    )
    mock_client.climate_command.reset_mock()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: "climate.test_my_climate", ATTR_PRESET_MODE: "preset1"},
        blocking=True,
    )
    mock_client.climate_command.assert_has_calls(
        [call(key=1, custom_preset="preset1", device_id=0)]
    )
    mock_client.climate_command.reset_mock()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: "climate.test_my_climate", ATTR_FAN_MODE: FAN_HIGH},
        blocking=True,
    )
    mock_client.climate_command.assert_has_calls(
        [call(key=1, fan_mode=ClimateFanMode.HIGH, device_id=0)]
    )
    mock_client.climate_command.reset_mock()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: "climate.test_my_climate", ATTR_FAN_MODE: "fan2"},
        blocking=True,
    )
    mock_client.climate_command.assert_has_calls(
        [call(key=1, custom_fan_mode="fan2", device_id=0)]
    )
    mock_client.climate_command.reset_mock()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_SWING_MODE,
        {ATTR_ENTITY_ID: "climate.test_my_climate", ATTR_SWING_MODE: SWING_BOTH},
        blocking=True,
    )
    mock_client.climate_command.assert_has_calls(
        [call(key=1, swing_mode=ClimateSwingMode.BOTH, device_id=0)]
    )
    mock_client.climate_command.reset_mock()


async def test_climate_entity_with_humidity(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test a generic climate entity with humidity."""
    entity_info = [
        ClimateInfo(
            object_id="myclimate",
            key=1,
            name="my climate",
            feature_flags=ClimateFeature.SUPPORTS_CURRENT_TEMPERATURE
            | ClimateFeature.SUPPORTS_TWO_POINT_TARGET_TEMPERATURE
            | ClimateFeature.SUPPORTS_CURRENT_HUMIDITY
            | ClimateFeature.SUPPORTS_TARGET_HUMIDITY
            | ClimateFeature.SUPPORTS_ACTION,
            visual_min_temperature=10.0,
            visual_max_temperature=30.0,
            visual_min_humidity=10.1,
            visual_max_humidity=29.7,
        )
    ]
    states = [
        ClimateState(
            key=1,
            mode=ClimateMode.AUTO,
            action=ClimateAction.COOLING,
            current_temperature=30,
            target_temperature=20,
            fan_mode=ClimateFanMode.AUTO,
            swing_mode=ClimateSwingMode.BOTH,
            current_humidity=20.1,
            target_humidity=25.7,
        )
    ]
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        states=states,
    )
    state = hass.states.get("climate.test_my_climate")
    assert state is not None
    assert state.state == HVACMode.AUTO
    attributes = state.attributes
    assert attributes[ATTR_CURRENT_HUMIDITY] == 20
    assert attributes[ATTR_HUMIDITY] == 26
    assert attributes[ATTR_MAX_HUMIDITY] == 30
    assert attributes[ATTR_MIN_HUMIDITY] == 10

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HUMIDITY,
        {ATTR_ENTITY_ID: "climate.test_my_climate", ATTR_HUMIDITY: 23},
        blocking=True,
    )
    mock_client.climate_command.assert_has_calls(
        [call(key=1, target_humidity=23, device_id=0)]
    )
    mock_client.climate_command.reset_mock()


async def test_climate_entity_with_heat(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test a generic climate entity with heat."""
    entity_info = [
        ClimateInfo(
            object_id="myclimate",
            key=1,
            name="my climate",
            feature_flags=ClimateFeature.SUPPORTS_CURRENT_TEMPERATURE
            | ClimateFeature.SUPPORTS_TWO_POINT_TARGET_TEMPERATURE
            | ClimateFeature.SUPPORTS_ACTION,
            visual_min_temperature=10.0,
            visual_max_temperature=30.0,
            supported_modes=[ClimateMode.COOL, ClimateMode.HEAT, ClimateMode.AUTO],
        )
    ]
    states = [
        ClimateState(
            key=1,
            mode=ClimateMode.HEAT,
            action=ClimateAction.HEATING,
            current_temperature=18,
            target_temperature=22,
        )
    ]
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        states=states,
    )
    state = hass.states.get("climate.test_my_climate")
    assert state is not None
    assert state.state == HVACMode.HEAT

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: "climate.test_my_climate", ATTR_TEMPERATURE: 23},
        blocking=True,
    )
    mock_client.climate_command.assert_has_calls(
        [call(key=1, target_temperature_low=23, device_id=0)]
    )
    mock_client.climate_command.reset_mock()


async def test_climate_entity_with_heat_cool(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test a generic climate entity with heat."""
    entity_info = [
        ClimateInfo(
            object_id="myclimate",
            key=1,
            name="my climate",
            feature_flags=ClimateFeature.SUPPORTS_CURRENT_TEMPERATURE
            | ClimateFeature.SUPPORTS_TWO_POINT_TARGET_TEMPERATURE
            | ClimateFeature.SUPPORTS_ACTION,
            visual_min_temperature=10.0,
            visual_max_temperature=30.0,
            supported_modes=[ClimateMode.COOL, ClimateMode.HEAT, ClimateMode.HEAT_COOL],
        )
    ]
    states = [
        ClimateState(
            key=1,
            mode=ClimateMode.HEAT_COOL,
            action=ClimateAction.HEATING,
            current_temperature=18,
            target_temperature=22,
        )
    ]
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        states=states,
    )
    state = hass.states.get("climate.test_my_climate")
    assert state is not None
    assert state.state == HVACMode.HEAT_COOL

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: "climate.test_my_climate",
            ATTR_TARGET_TEMP_HIGH: 23,
            ATTR_TARGET_TEMP_LOW: 20,
        },
        blocking=True,
    )
    mock_client.climate_command.assert_has_calls(
        [
            call(
                key=1,
                target_temperature_high=23,
                target_temperature_low=20,
                device_id=0,
            )
        ]
    )
    mock_client.climate_command.reset_mock()


async def test_climate_set_temperature_unsupported_mode(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test setting temperature in unsupported mode with two-point temperature support."""
    entity_info = [
        ClimateInfo(
            object_id="myclimate",
            key=1,
            name="my climate",
            feature_flags=ClimateFeature.SUPPORTS_TWO_POINT_TARGET_TEMPERATURE,
            supported_modes=[ClimateMode.HEAT, ClimateMode.COOL, ClimateMode.AUTO],
            visual_min_temperature=10.0,
            visual_max_temperature=30.0,
        )
    ]
    states = [
        ClimateState(
            key=1,
            mode=ClimateMode.AUTO,
            target_temperature=20,
        )
    ]
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        states=states,
    )

    with pytest.raises(
        ServiceValidationError,
        match="Setting target_temperature is only supported in heat or cool modes",
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: "climate.test_my_climate",
                ATTR_TEMPERATURE: 25,
            },
            blocking=True,
        )

    mock_client.climate_command.assert_not_called()


async def test_climate_entity_with_inf_value(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test a generic climate entity with infinite temp."""
    entity_info = [
        ClimateInfo(
            object_id="myclimate",
            key=1,
            name="my climate",
            feature_flags=ClimateFeature.SUPPORTS_CURRENT_TEMPERATURE
            | ClimateFeature.SUPPORTS_TWO_POINT_TARGET_TEMPERATURE
            | ClimateFeature.SUPPORTS_CURRENT_HUMIDITY
            | ClimateFeature.SUPPORTS_TARGET_HUMIDITY
            | ClimateFeature.SUPPORTS_ACTION,
            visual_min_temperature=10.0,
            visual_max_temperature=30.0,
            visual_min_humidity=10.1,
            visual_max_humidity=29.7,
        )
    ]
    states = [
        ClimateState(
            key=1,
            mode=ClimateMode.AUTO,
            action=ClimateAction.COOLING,
            current_temperature=math.inf,
            target_temperature=math.inf,
            fan_mode=ClimateFanMode.AUTO,
            swing_mode=ClimateSwingMode.BOTH,
            current_humidity=math.inf,
            target_humidity=25.7,
        )
    ]
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        states=states,
    )
    state = hass.states.get("climate.test_my_climate")
    assert state is not None
    assert state.state == HVACMode.AUTO
    attributes = state.attributes
    assert ATTR_CURRENT_HUMIDITY not in attributes
    assert attributes[ATTR_HUMIDITY] == 26
    assert attributes[ATTR_MAX_HUMIDITY] == 30
    assert attributes[ATTR_MIN_HUMIDITY] == 10
    assert attributes[ATTR_TEMPERATURE] is None
    assert attributes[ATTR_CURRENT_TEMPERATURE] is None


async def test_climate_entity_attributes(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
    snapshot: SnapshotAssertion,
) -> None:
    """Test a climate entity sets correct attributes."""
    entity_info = [
        ClimateInfo(
            object_id="myclimate",
            key=1,
            name="my climate",
            feature_flags=ClimateFeature.SUPPORTS_CURRENT_TEMPERATURE
            | ClimateFeature.SUPPORTS_ACTION,
            visual_target_temperature_step=2,
            visual_current_temperature_step=2,
            visual_min_temperature=10.0,
            visual_max_temperature=30.0,
            supported_fan_modes=[ClimateFanMode.LOW, ClimateFanMode.HIGH],
            supported_modes=[
                ClimateMode.COOL,
                ClimateMode.HEAT,
                ClimateMode.AUTO,
                ClimateMode.OFF,
            ],
            supported_presets=[ClimatePreset.AWAY, ClimatePreset.ACTIVITY],
            supported_custom_presets=["preset1", "preset2"],
            supported_custom_fan_modes=["fan1", "fan2"],
            supported_swing_modes=[ClimateSwingMode.BOTH, ClimateSwingMode.OFF],
        )
    ]
    states = [
        ClimateState(
            key=1,
            mode=ClimateMode.COOL,
            action=ClimateAction.COOLING,
            current_temperature=30,
            target_temperature=20,
            fan_mode=ClimateFanMode.AUTO,
            swing_mode=ClimateSwingMode.BOTH,
        )
    ]
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        states=states,
    )
    state = hass.states.get("climate.test_my_climate")
    assert state is not None
    assert state.state == HVACMode.COOL
    assert state.attributes == snapshot(name="climate-entity-attributes")


async def test_climate_entity_attribute_current_temperature_unsupported(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test a climate entity with current temperature unsupported."""
    entity_info = [
        ClimateInfo(
            object_id="myclimate",
            key=1,
            name="my climate",
            supports_current_temperature=False,
        )
    ]
    states = [
        ClimateState(
            key=1,
            current_temperature=30,
        )
    ]
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        states=states,
    )
    state = hass.states.get("climate.test_my_climate")
    assert state is not None
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] is None
