"""Tests for Zentraly thermostat modes and setpoints."""

from contextlib import AbstractContextManager, nullcontext
from unittest.mock import MagicMock, call, patch

import pytest
from zentraly import (
    ClimateCapability,
    ClimateOperationMode,
    DeviceModel,
    ZentralyClimateApi,
    get_device_commands,
)

from homeassistant.components.climate import (
    PRESET_AWAY,
    PRESET_NONE,
    HVACAction,
    HVACMode,
)
from homeassistant.components.zentraly.climate import ZentralyClimate
from homeassistant.exceptions import HomeAssistantError


@pytest.mark.parametrize(
    ("mode", "operation"),
    [
        pytest.param(HVACMode.OFF, ClimateOperationMode.OFF, id="off"),
        pytest.param(HVACMode.HEAT, ClimateOperationMode.MANUAL, id="heat"),
        pytest.param(HVACMode.AUTO, ClimateOperationMode.AUTO, id="auto"),
    ],
)
async def test_hvac_mode(
    platform_device: MagicMock, mode: HVACMode, operation: ClimateOperationMode
) -> None:
    """Translate Home Assistant modes into device operations."""
    api = MagicMock(spec=ZentralyClimateApi)
    api.configuration = get_device_commands(DeviceModel.ZTTIN).climate_configuration
    api.supports.return_value = True
    api.async_set_operation_mode.return_value = True
    entity = ZentralyClimate(platform_device, climate_api=api)
    with patch.object(entity, "async_write_ha_state"):
        await entity.async_set_hvac_mode(mode)
    assert entity.hvac_mode == mode
    api.async_set_operation_mode.assert_awaited_once_with(operation)


@pytest.mark.parametrize(
    ("success", "expected", "expectation"),
    [
        pytest.param(True, 22.0, nullcontext(), id="success"),
        pytest.param(False, 20.0, pytest.raises(HomeAssistantError), id="failure"),
    ],
)
async def test_temperature_write(
    platform_device: MagicMock,
    success: bool,
    expected: float,
    expectation: AbstractContextManager,
) -> None:
    """A failed setpoint write preserves the last reported temperature."""
    api = MagicMock(spec=ZentralyClimateApi)
    api.configuration = get_device_commands(DeviceModel.ZTTIN).climate_configuration
    api.supports.return_value = True
    api.async_set_target_temperature.return_value = success
    entity = ZentralyClimate(platform_device, climate_api=api)
    with patch.object(entity, "async_write_ha_state"):
        entity._handle_state_update({ClimateCapability.TARGET_TEMPERATURE: 20.0})
        with expectation:
            await entity.async_set_temperature(temperature=22.0)
    assert entity.target_temperature == expected
    api.async_set_target_temperature.assert_awaited_once_with(22.0)


def test_away_report(platform_device: MagicMock) -> None:
    """Away mode displays its setpoint and preserves the reported heat demand."""
    api = MagicMock(spec=ZentralyClimateApi)
    api.configuration = get_device_commands(DeviceModel.ZTTIN).climate_configuration
    api.supports.return_value = True
    entity = ZentralyClimate(platform_device, climate_api=api)
    with patch.object(entity, "async_write_ha_state"):
        entity._handle_state_update(
            {
                ClimateCapability.LOCAL_TEMPERATURE: 19.0,
                ClimateCapability.TARGET_TEMPERATURE: 22.0,
                ClimateCapability.OPERATION_MODE: ClimateOperationMode.AWAY,
                ClimateCapability.HEAT_DEMAND: True,
            }
        )
    assert entity.current_temperature == 19.0
    assert entity.target_temperature == 22.0
    assert entity.preset_mode == PRESET_AWAY
    assert entity.hvac_action == HVACAction.HEATING


async def test_missing_readings_clear_previous_values(
    platform_device: MagicMock,
) -> None:
    """Unknown readings do not retain stale temperatures or imply an outage."""
    api = MagicMock(spec=ZentralyClimateApi)
    api.configuration = get_device_commands(DeviceModel.ZTTIN).climate_configuration
    api.supports.return_value = True
    api.async_get_current_temperature.return_value = None
    api.async_get_target_temperature.return_value = None
    api.async_get_operation_mode.return_value = None
    api.async_get_humidity.return_value = None
    api.async_get_heat_demand.return_value = None
    entity = ZentralyClimate(platform_device, climate_api=api)
    with patch.object(entity, "async_write_ha_state"):
        entity._handle_state_update(
            {
                ClimateCapability.LOCAL_TEMPERATURE: 19.0,
                ClimateCapability.TARGET_TEMPERATURE: 22.0,
                ClimateCapability.OPERATION_MODE: ClimateOperationMode.AWAY,
                ClimateCapability.HEAT_DEMAND: True,
            }
        )
    await entity.async_update()
    assert entity.available
    assert entity.current_temperature is None
    assert entity.target_temperature is None
    assert entity.current_humidity is None
    assert entity.hvac_mode is None
    assert entity.hvac_action is None


@pytest.mark.parametrize(
    ("mode", "operation"),
    [
        pytest.param(HVACMode.AUTO, ClimateOperationMode.AUTO, id="auto"),
        pytest.param(HVACMode.OFF, ClimateOperationMode.OFF, id="off"),
        pytest.param(HVACMode.HEAT, ClimateOperationMode.MANUAL, id="heat"),
    ],
)
async def test_temperature_with_explicit_mode(
    platform_device: MagicMock, mode: HVACMode, operation: ClimateOperationMode
) -> None:
    """Apply the requested mode after the setpoint's manual-mode side effect."""
    api = MagicMock(spec=ZentralyClimateApi)
    api.configuration = get_device_commands(DeviceModel.ZTTIN).climate_configuration
    api.supports.return_value = True
    api.async_set_target_temperature.return_value = True
    api.async_set_operation_mode.return_value = True
    writes = MagicMock()
    writes.attach_mock(api.async_set_target_temperature, "temperature")
    writes.attach_mock(api.async_set_operation_mode, "mode")
    entity = ZentralyClimate(platform_device, climate_api=api)
    with patch.object(entity, "async_write_ha_state"):
        await entity.async_set_temperature(temperature=22.0, hvac_mode=mode)
    assert entity.target_temperature == 22.0
    assert entity.hvac_mode == mode
    assert writes.mock_calls == [
        call.temperature(22.0),
        call.mode(operation),
    ]


@pytest.mark.parametrize(
    ("success", "preset", "expectation"),
    [
        pytest.param(True, PRESET_NONE, nullcontext(), id="success"),
        pytest.param(
            False, PRESET_AWAY, pytest.raises(HomeAssistantError), id="failure"
        ),
    ],
)
async def test_exit_away_preset(
    platform_device: MagicMock,
    success: bool,
    preset: str,
    expectation: AbstractContextManager,
) -> None:
    """Only a confirmed write leaves Away and selects manual operation."""
    api = MagicMock(spec=ZentralyClimateApi)
    api.configuration = get_device_commands(DeviceModel.ZTTIN).climate_configuration
    api.supports.return_value = True
    api.async_set_operation_mode.return_value = success
    entity = ZentralyClimate(platform_device, climate_api=api)
    with patch.object(entity, "async_write_ha_state"):
        entity._handle_state_update(
            {ClimateCapability.OPERATION_MODE: ClimateOperationMode.AWAY}
        )
        with expectation:
            await entity.async_set_preset_mode(PRESET_NONE)
    assert entity.preset_mode == preset
    api.async_set_operation_mode.assert_awaited_once_with(ClimateOperationMode.MANUAL)
