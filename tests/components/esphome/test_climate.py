"""Test ESPHome climates."""


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

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    ATTR_SWING_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ATTR_TEMPERATURE,
    DOMAIN as CLIMATE_DOMAIN,
    FAN_HIGH,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
    SWING_BOTH,
    HVACMode,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant


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
            supports_two_point_target_temperature=True,
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

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: "climate.test_myclimate", ATTR_TEMPERATURE: 25},
        blocking=True,
    )
    mock_client.climate_command.assert_has_calls([call(key=1, target_temperature=25.0)])
    mock_client.climate_command.reset_mock()

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
        {ATTR_ENTITY_ID: "climate.test_myclimate", ATTR_TEMPERATURE: 25},
        blocking=True,
    )
    mock_client.climate_command.assert_has_calls([call(key=1, target_temperature=25.0)])
    mock_client.climate_command.reset_mock()

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
