"""Test ESPHome climates."""

import math
from unittest.mock import call

from aioesphomeapi import (
    APIClient,
    ClimateAction,
    ClimateFanMode,
    ClimateInfo,
    ClimateMode,
    ClimatePreset,
    ClimateState,
    ClimateSwingMode,
)
import pytest
from syrupy import SnapshotAssertion

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


async def test_climate_entity(
    hass: HomeAssistant, mock_client: APIClient, mock_generic_device_entry
) -> None:
    """Test a generic climate entity."""
    entity_info = [
        ClimateInfo(
            object_id="myclimate",
            key=1,
            name="my climate",
            unique_id="my_climate",
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
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("climate.test_myclimate")
    assert state is not None
    assert state.state == HVACMode.COOL

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: "climate.test_myclimate", ATTR_TEMPERATURE: 25},
        blocking=True,
    )
    mock_client.climate_command.assert_has_calls([call(key=1, target_temperature=25.0)])
    mock_client.climate_command.reset_mock()


async def test_climate_entity_with_step_and_two_point(
    hass: HomeAssistant, mock_client: APIClient, mock_generic_device_entry
) -> None:
    """Test a generic climate entity."""
    entity_info = [
        ClimateInfo(
            object_id="myclimate",
            key=1,
            name="my climate",
            unique_id="my_climate",
            supports_current_temperature=True,
            supports_two_point_target_temperature=True,
            visual_target_temperature_step=2,
            visual_current_temperature_step=2,
            supports_action=False,
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
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("climate.test_myclimate")
    assert state is not None
    assert state.state == HVACMode.COOL

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: "climate.test_myclimate", ATTR_TEMPERATURE: 25},
            blocking=True,
        )

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: "climate.test_myclimate",
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
            )
        ]
    )
    mock_client.climate_command.reset_mock()


async def test_climate_entity_with_step_and_target_temp(
    hass: HomeAssistant, mock_client: APIClient, mock_generic_device_entry
) -> None:
    """Test a generic climate entity."""
    entity_info = [
        ClimateInfo(
            object_id="myclimate",
            key=1,
            name="my climate",
            unique_id="my_climate",
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
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("climate.test_myclimate")
    assert state is not None
    assert state.state == HVACMode.COOL

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: "climate.test_myclimate",
            ATTR_HVAC_MODE: HVACMode.AUTO,
            ATTR_TEMPERATURE: 25,
        },
        blocking=True,
    )
    mock_client.climate_command.assert_has_calls(
        [call(key=1, mode=ClimateMode.AUTO, target_temperature=25.0)]
    )
    mock_client.climate_command.reset_mock()

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: "climate.test_myclimate",
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
            ATTR_ENTITY_ID: "climate.test_myclimate",
            ATTR_HVAC_MODE: HVACMode.HEAT,
        },
        blocking=True,
    )
    mock_client.climate_command.assert_has_calls(
        [
            call(
                key=1,
                mode=ClimateMode.HEAT,
            )
        ]
    )
    mock_client.climate_command.reset_mock()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: "climate.test_myclimate", ATTR_PRESET_MODE: "away"},
        blocking=True,
    )
    mock_client.climate_command.assert_has_calls(
        [
            call(
                key=1,
                preset=ClimatePreset.AWAY,
            )
        ]
    )
    mock_client.climate_command.reset_mock()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: "climate.test_myclimate", ATTR_PRESET_MODE: "preset1"},
        blocking=True,
    )
    mock_client.climate_command.assert_has_calls([call(key=1, custom_preset="preset1")])
    mock_client.climate_command.reset_mock()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: "climate.test_myclimate", ATTR_FAN_MODE: FAN_HIGH},
        blocking=True,
    )
    mock_client.climate_command.assert_has_calls(
        [call(key=1, fan_mode=ClimateFanMode.HIGH)]
    )
    mock_client.climate_command.reset_mock()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: "climate.test_myclimate", ATTR_FAN_MODE: "fan2"},
        blocking=True,
    )
    mock_client.climate_command.assert_has_calls([call(key=1, custom_fan_mode="fan2")])
    mock_client.climate_command.reset_mock()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_SWING_MODE,
        {ATTR_ENTITY_ID: "climate.test_myclimate", ATTR_SWING_MODE: SWING_BOTH},
        blocking=True,
    )
    mock_client.climate_command.assert_has_calls(
        [call(key=1, swing_mode=ClimateSwingMode.BOTH)]
    )
    mock_client.climate_command.reset_mock()


async def test_climate_entity_with_humidity(
    hass: HomeAssistant, mock_client: APIClient, mock_generic_device_entry
) -> None:
    """Test a generic climate entity with humidity."""
    entity_info = [
        ClimateInfo(
            object_id="myclimate",
            key=1,
            name="my climate",
            unique_id="my_climate",
            supports_current_temperature=True,
            supports_two_point_target_temperature=True,
            supports_action=True,
            visual_min_temperature=10.0,
            visual_max_temperature=30.0,
            supports_current_humidity=True,
            supports_target_humidity=True,
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
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("climate.test_myclimate")
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
        {ATTR_ENTITY_ID: "climate.test_myclimate", ATTR_HUMIDITY: 23},
        blocking=True,
    )
    mock_client.climate_command.assert_has_calls([call(key=1, target_humidity=23)])
    mock_client.climate_command.reset_mock()


async def test_climate_entity_with_inf_value(
    hass: HomeAssistant, mock_client: APIClient, mock_generic_device_entry
) -> None:
    """Test a generic climate entity with infinite temp."""
    entity_info = [
        ClimateInfo(
            object_id="myclimate",
            key=1,
            name="my climate",
            unique_id="my_climate",
            supports_current_temperature=True,
            supports_two_point_target_temperature=True,
            supports_action=True,
            visual_min_temperature=10.0,
            visual_max_temperature=30.0,
            supports_current_humidity=True,
            supports_target_humidity=True,
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
            current_humidity=20.1,
            target_humidity=25.7,
        )
    ]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("climate.test_myclimate")
    assert state is not None
    assert state.state == HVACMode.AUTO
    attributes = state.attributes
    assert attributes[ATTR_CURRENT_HUMIDITY] == 20
    assert attributes[ATTR_HUMIDITY] == 26
    assert attributes[ATTR_MAX_HUMIDITY] == 30
    assert attributes[ATTR_MIN_HUMIDITY] == 10
    assert ATTR_TEMPERATURE not in attributes
    assert attributes[ATTR_CURRENT_TEMPERATURE] is None


async def test_climate_entity_attributes(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test a climate entity sets correct attributes."""
    entity_info = [
        ClimateInfo(
            object_id="myclimate",
            key=1,
            name="my climate",
            unique_id="my_climate",
            supports_current_temperature=True,
            visual_target_temperature_step=2,
            visual_current_temperature_step=2,
            supports_action=True,
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
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("climate.test_myclimate")
    assert state is not None
    assert state.state == HVACMode.COOL
    assert state.attributes == snapshot(name="climate-entity-attributes")
