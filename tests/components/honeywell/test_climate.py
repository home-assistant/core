"""Test the Honeywell climate domain."""

from contextlib import AbstractContextManager, nullcontext as does_not_raise
import datetime as dt
from unittest.mock import MagicMock, _Call, call

from aiohttp import ClientConnectionError
import aiosomecomfort
from freezegun.api import FrozenDateTimeFactory
import probatio
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.climate import (
    ATTR_PRESET_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    FAN_AUTO,
    FAN_DIFFUSE,
    FAN_ON,
    PRESET_AWAY,
    PRESET_NONE,
    ClimateService,
    ClimateServiceArgument,
    HVACMode,
)
from homeassistant.components.honeywell.climate import (
    DOMAIN,
    MODE_PERMANENT_HOLD,
    MODE_TEMPORARY_HOLD,
    PRESET_HOLD,
    RETRY,
    SCAN_INTERVAL,
)
from homeassistant.components.honeywell.services import (
    HoneywellService,
    HoneywellServiceArgument,
)
from homeassistant.const import Platform, TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import utcnow

from . import init_integration, reset_mock

FAN_ACTION = "fan_action"
ENTITY_ID = "climate.device1"


async def test_no_thermostat_options(
    hass: HomeAssistant, device: MagicMock, config_entry: MagicMock
) -> None:
    """Test climate entity setup without additional options."""
    device._data = {}
    await init_integration(hass, config_entry)
    assert hass.states.get("climate.device1")
    assert hass.states.get("sensor.device1_temperature")
    assert hass.states.get("sensor.device1_humidity")


async def test_static_attributes(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device: MagicMock,
    config_entry: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test static climate attributes."""
    await init_integration(hass, config_entry)

    entity_id = f"climate.{device.name}"
    entry = entity_registry.async_get(entity_id)
    assert entry

    state = hass.states.get(entity_id)
    assert state.state == HVACMode.OFF

    attributes = state.attributes

    assert attributes == snapshot(exclude=props("dr_phase"))


async def test_dynamic_attributes(
    hass: HomeAssistant, device: MagicMock, config_entry: MagicMock
) -> None:
    """Test dynamic attributes."""
    await init_integration(hass, config_entry)

    entity_id = f"climate.{device.name}"
    state = hass.states.get(entity_id)
    assert state.state == HVACMode.OFF
    attributes = state.attributes
    assert attributes["current_temperature"] == 20
    assert attributes["current_humidity"] == 50

    device.system_mode = "cool"
    device.current_temperature = 21
    device.current_humidity = 55

    async_fire_time_changed(
        hass,
        utcnow() + SCAN_INTERVAL,
    )
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == HVACMode.COOL
    attributes = state.attributes
    assert attributes["current_temperature"] == 21
    assert attributes["current_humidity"] == 55

    device.system_mode = "heat"
    device.current_temperature = 61
    device.current_humidity = 50

    async_fire_time_changed(
        hass,
        utcnow() + SCAN_INTERVAL,
    )
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == HVACMode.HEAT
    attributes = state.attributes
    assert attributes["current_temperature"] == 61
    assert attributes["current_humidity"] == 50

    device.system_mode = "auto"

    async_fire_time_changed(
        hass,
        utcnow() + SCAN_INTERVAL,
    )
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == HVACMode.HEAT_COOL
    attributes = state.attributes
    assert attributes["current_temperature"] == 61
    assert attributes["current_humidity"] == 50


async def test_mode_service_calls(
    hass: HomeAssistant,
    device: MagicMock,
    config_entry: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test controlling the entity mode through service calls."""
    await init_integration(hass, config_entry)
    entity_id = f"climate.{device.name}"

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.TURN_OFF,
        {TargetKey.ENTITY_ID: entity_id},
        blocking=True,
    )
    device.set_system_mode.assert_called_once_with("off")

    device.set_system_mode.reset_mock()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.TURN_ON,
        {TargetKey.ENTITY_ID: entity_id},
        blocking=True,
    )
    device.set_system_mode.assert_called_once_with("auto")

    device.set_system_mode.reset_mock()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.SET_HVAC_MODE,
        {
            TargetKey.ENTITY_ID: entity_id,
            ClimateServiceArgument.HVAC_MODE: HVACMode.COOL,
        },
        blocking=True,
    )
    device.set_system_mode.assert_called_once_with("cool")

    device.set_system_mode.reset_mock()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.SET_HVAC_MODE,
        {
            TargetKey.ENTITY_ID: entity_id,
            ClimateServiceArgument.HVAC_MODE: HVACMode.HEAT,
        },
        blocking=True,
    )
    device.set_system_mode.assert_called_once_with("heat")

    device.set_system_mode.reset_mock()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.SET_HVAC_MODE,
        {
            TargetKey.ENTITY_ID: entity_id,
            ClimateServiceArgument.HVAC_MODE: HVACMode.HEAT_COOL,
        },
        blocking=True,
    )
    device.set_system_mode.assert_called_once_with("auto")

    device.set_system_mode.reset_mock()
    device.set_system_mode.side_effect = aiosomecomfort.SomeComfortError
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_HVAC_MODE,
            {
                TargetKey.ENTITY_ID: entity_id,
                ClimateServiceArgument.HVAC_MODE: HVACMode.HEAT_COOL,
            },
            blocking=True,
        )
    device.set_system_mode.assert_called_once_with("auto")

    device.set_system_mode.reset_mock()
    device.set_system_mode.side_effect = aiosomecomfort.UnexpectedResponse
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_HVAC_MODE,
            {
                TargetKey.ENTITY_ID: entity_id,
                ClimateServiceArgument.HVAC_MODE: HVACMode.HEAT_COOL,
            },
            blocking=True,
        )


async def test_fan_modes_service_calls(
    hass: HomeAssistant, device: MagicMock, config_entry: MagicMock
) -> None:
    """Test controlling the fan modes through service calls."""
    await init_integration(hass, config_entry)
    entity_id = f"climate.{device.name}"

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.SET_FAN_MODE,
        {TargetKey.ENTITY_ID: entity_id, ClimateServiceArgument.FAN_MODE: FAN_AUTO},
        blocking=True,
    )

    device.set_fan_mode.assert_called_once_with("auto")

    device.set_fan_mode.reset_mock()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.SET_FAN_MODE,
        {TargetKey.ENTITY_ID: entity_id, ClimateServiceArgument.FAN_MODE: FAN_ON},
        blocking=True,
    )

    device.set_fan_mode.assert_called_once_with("on")

    device.set_fan_mode.reset_mock()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.SET_FAN_MODE,
        {TargetKey.ENTITY_ID: entity_id, ClimateServiceArgument.FAN_MODE: FAN_DIFFUSE},
        blocking=True,
    )

    device.set_fan_mode.assert_called_once_with("circulate")

    device.set_fan_mode.reset_mock()

    device.set_fan_mode.side_effect = aiosomecomfort.SomeComfortError
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_FAN_MODE,
            {
                TargetKey.ENTITY_ID: entity_id,
                ClimateServiceArgument.FAN_MODE: FAN_DIFFUSE,
            },
            blocking=True,
        )

    device.set_fan_mode.side_effect = aiosomecomfort.UnexpectedResponse
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_FAN_MODE,
            {
                TargetKey.ENTITY_ID: entity_id,
                ClimateServiceArgument.FAN_MODE: FAN_DIFFUSE,
            },
            blocking=True,
        )


async def test_service_calls_off_mode(
    hass: HomeAssistant,
    device: MagicMock,
    config_entry: MagicMock,
) -> None:
    """Test controlling the entity through service calls."""

    device.system_mode = "off"

    await init_integration(hass, config_entry)
    entity_id = f"climate.{device.name}"

    async_fire_time_changed(
        hass,
        utcnow() + SCAN_INTERVAL,
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.SET_TEMPERATURE,
        {TargetKey.ENTITY_ID: entity_id, ClimateServiceArgument.TEMPERATURE: 35},
        blocking=True,
    )

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.SET_TEMPERATURE,
        {
            TargetKey.ENTITY_ID: entity_id,
            ClimateServiceArgument.TARGET_TEMP_LOW: 25.0,
            ClimateServiceArgument.TARGET_TEMP_HIGH: 35.0,
        },
        blocking=True,
    )
    device.set_setpoint_cool.assert_called_with(35)
    device.set_setpoint_heat.assert_called_with(25)

    device.set_setpoint_heat.reset_mock()
    device.set_setpoint_heat.side_effect = aiosomecomfort.SomeComfortError

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_TEMPERATURE,
            {
                TargetKey.ENTITY_ID: entity_id,
                ClimateServiceArgument.TARGET_TEMP_LOW: 24.0,
                ClimateServiceArgument.TARGET_TEMP_HIGH: 34.0,
            },
            blocking=True,
        )
    device.set_setpoint_cool.assert_called_with(34)
    device.set_setpoint_heat.assert_called_with(24)
    assert exc_info.value.translation_key == "temp_failed_value"

    device.set_setpoint_heat.reset_mock()
    device.set_setpoint_heat.side_effect = aiosomecomfort.UnexpectedResponse

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_TEMPERATURE,
            {
                TargetKey.ENTITY_ID: entity_id,
                ClimateServiceArgument.TARGET_TEMP_LOW: 25.0,
                ClimateServiceArgument.TARGET_TEMP_HIGH: 35.0,
            },
            blocking=True,
        )
    device.set_setpoint_cool.assert_called_with(35)
    device.set_setpoint_heat.assert_called_with(25)

    reset_mock(device)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.SET_TEMPERATURE,
        {TargetKey.ENTITY_ID: entity_id, ClimateServiceArgument.TEMPERATURE: 35},
        blocking=True,
    )
    device.set_setpoint_heat.assert_not_called()
    device.set_setpoint_cool.assert_not_called()

    reset_mock(device)
    device.raw_ui_data["StatusHeat"] = 2
    device.raw_ui_data["StatusCool"] = 2

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.SET_PRESET_MODE,
        {
            TargetKey.ENTITY_ID: entity_id,
            ClimateServiceArgument.PRESET_MODE: PRESET_HOLD,
        },
        blocking=True,
    )

    device.set_hold_cool.assert_not_called()
    device.set_hold_heat.assert_not_called()

    reset_mock(device)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.SET_PRESET_MODE,
        {
            TargetKey.ENTITY_ID: entity_id,
            ClimateServiceArgument.PRESET_MODE: PRESET_AWAY,
        },
        blocking=True,
    )

    device.set_hold_cool.assert_not_called()
    device.set_setpoint_cool.assert_not_called()
    device.set_hold_heat.assert_not_called()
    device.set_setpoint_heat.assert_not_called()

    device.set_hold_heat.reset_mock()
    device.set_hold_cool.reset_mock()

    device.set_setpoint_cool.reset_mock()
    device.set_setpoint_heat.reset_mock()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.SET_PRESET_MODE,
        {
            TargetKey.ENTITY_ID: entity_id,
            ClimateServiceArgument.PRESET_MODE: PRESET_NONE,
        },
        blocking=True,
    )

    device.set_hold_heat.assert_called_once_with(False)
    device.set_hold_cool.assert_called_once_with(False)

    device.set_hold_heat.reset_mock()
    device.set_hold_cool.reset_mock()

    device.set_setpoint_cool.reset_mock()
    device.set_setpoint_heat.reset_mock()

    reset_mock(device)

    device.raw_ui_data["StatusHeat"] = 2
    device.raw_ui_data["StatusCool"] = 2

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.SET_PRESET_MODE,
        {
            TargetKey.ENTITY_ID: entity_id,
            ClimateServiceArgument.PRESET_MODE: PRESET_HOLD,
        },
        blocking=True,
    )

    device.set_hold_heat.assert_not_called()
    device.set_hold_cool.assert_not_called()

    reset_mock(device)
    device.set_hold_heat.side_effect = aiosomecomfort.SomeComfortError
    device.raw_ui_data["StatusHeat"] = 2
    device.raw_ui_data["StatusCool"] = 2
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.SET_PRESET_MODE,
        {
            TargetKey.ENTITY_ID: entity_id,
            ClimateServiceArgument.PRESET_MODE: PRESET_HOLD,
        },
        blocking=True,
    )

    device.set_hold_heat.assert_not_called()
    device.set_hold_cool.assert_not_called()


async def test_service_calls_cool_mode(
    hass: HomeAssistant,
    device: MagicMock,
    config_entry: MagicMock,
) -> None:
    """Test controlling the entity through service calls."""

    device.system_mode = "cool"

    await init_integration(hass, config_entry)
    entity_id = f"climate.{device.name}"

    async_fire_time_changed(
        hass,
        utcnow() + SCAN_INTERVAL,
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.SET_TEMPERATURE,
        {TargetKey.ENTITY_ID: entity_id, ClimateServiceArgument.TEMPERATURE: 15},
        blocking=True,
    )
    device.set_hold_cool.assert_called_once_with(dt.time(2, 30), 15)
    device.set_hold_cool.reset_mock()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.SET_TEMPERATURE,
        {
            TargetKey.ENTITY_ID: entity_id,
            ClimateServiceArgument.TARGET_TEMP_LOW: 15.0,
            ClimateServiceArgument.TARGET_TEMP_HIGH: 20.0,
        },
        blocking=True,
    )
    device.set_setpoint_cool.assert_called_with(20)
    device.set_setpoint_heat.assert_called_with(15)

    device.set_setpoint_cool.reset_mock()
    device.set_setpoint_cool.side_effect = aiosomecomfort.SomeComfortError

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_TEMPERATURE,
            {
                TargetKey.ENTITY_ID: entity_id,
                ClimateServiceArgument.TARGET_TEMP_LOW: 15.0,
                ClimateServiceArgument.TARGET_TEMP_HIGH: 20.0,
            },
            blocking=True,
        )
    device.set_setpoint_cool.assert_called_with(20)
    device.set_setpoint_heat.assert_called_with(15)
    assert exc_info.value.translation_key == "temp_failed_value"

    reset_mock(device)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.SET_PRESET_MODE,
        {
            TargetKey.ENTITY_ID: entity_id,
            ClimateServiceArgument.PRESET_MODE: PRESET_AWAY,
        },
        blocking=True,
    )

    device.set_hold_cool.assert_called_once_with(True, 12)
    device.set_hold_heat.assert_not_called()
    device.set_setpoint_heat.assert_not_called()

    reset_mock(device)

    device.set_hold_cool.side_effect = aiosomecomfort.SomeComfortError

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_PRESET_MODE,
            {
                TargetKey.ENTITY_ID: entity_id,
                ClimateServiceArgument.PRESET_MODE: PRESET_AWAY,
            },
            blocking=True,
        )

    device.set_hold_cool.assert_called_once_with(True, 12)
    device.set_hold_heat.assert_not_called()
    device.set_setpoint_heat.assert_not_called()
    assert exc_info.value.translation_key == "temp_failed_range"

    reset_mock(device)

    device.raw_ui_data["StatusHeat"] = 2
    device.raw_ui_data["StatusCool"] = 2

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_PRESET_MODE,
            {
                TargetKey.ENTITY_ID: entity_id,
                ClimateServiceArgument.PRESET_MODE: PRESET_HOLD,
            },
            blocking=True,
        )

    device.set_hold_cool.assert_called_once_with(True)
    device.set_hold_heat.assert_not_called()

    device.hold_heat = True
    device.hold_cool = True

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_TEMPERATURE,
            {TargetKey.ENTITY_ID: entity_id, ClimateServiceArgument.TEMPERATURE: "20"},
            blocking=True,
        )

    device.set_setpoint_cool.assert_called_once()

    reset_mock(device)
    device.set_hold_cool.side_effect = aiosomecomfort.SomeComfortError

    device.raw_ui_data["StatusHeat"] = 2
    device.raw_ui_data["StatusCool"] = 2
    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_PRESET_MODE,
            {
                TargetKey.ENTITY_ID: entity_id,
                ClimateServiceArgument.PRESET_MODE: PRESET_HOLD,
            },
            blocking=True,
        )
    device.set_hold_cool.assert_called_once_with(True)
    device.set_hold_heat.assert_not_called()
    assert exc_info.value.translation_key == "set_hold_failed"

    reset_mock(device)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_PRESET_MODE,
            {
                TargetKey.ENTITY_ID: entity_id,
                ClimateServiceArgument.PRESET_MODE: PRESET_NONE,
            },
            blocking=True,
        )

    device.set_hold_heat.assert_not_called()
    device.set_hold_cool.assert_called_once_with(False)

    reset_mock(device)

    device.set_hold_cool.side_effect = aiosomecomfort.SomeComfortError
    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_PRESET_MODE,
            {
                TargetKey.ENTITY_ID: entity_id,
                ClimateServiceArgument.PRESET_MODE: PRESET_NONE,
            },
            blocking=True,
        )

    device.set_hold_heat.assert_not_called()
    device.set_hold_cool.assert_called_once_with(False)
    assert exc_info.value.translation_key == "stop_hold_failed"

    reset_mock(device)

    device.raw_ui_data["StatusHeat"] = 2
    device.raw_ui_data["StatusCool"] = 2

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_PRESET_MODE,
            {
                TargetKey.ENTITY_ID: entity_id,
                ClimateServiceArgument.PRESET_MODE: PRESET_HOLD,
            },
            blocking=True,
        )

    device.set_hold_cool.assert_called_once_with(True)
    device.set_hold_heat.assert_not_called()

    reset_mock(device)

    device.set_hold_cool.side_effect = aiosomecomfort.SomeComfortError

    device.raw_ui_data["StatusHeat"] = 2
    device.raw_ui_data["StatusCool"] = 2
    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_PRESET_MODE,
            {
                TargetKey.ENTITY_ID: entity_id,
                ClimateServiceArgument.PRESET_MODE: PRESET_HOLD,
            },
            blocking=True,
        )

    device.set_hold_cool.assert_called_once_with(True)
    device.set_hold_heat.assert_not_called()
    assert exc_info.value.translation_key == "set_hold_failed"

    reset_mock(device)

    device.raw_ui_data["StatusHeat"] = 2
    device.raw_ui_data["StatusCool"] = 2
    device.system_mode = "Junk"

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_PRESET_MODE,
            {
                TargetKey.ENTITY_ID: entity_id,
                ClimateServiceArgument.PRESET_MODE: PRESET_HOLD,
            },
            blocking=True,
        )

    device.set_hold_cool.assert_not_called()
    device.set_hold_heat.assert_not_called()
    assert exc_info.value.translation_key == "set_mode_failed"


async def test_service_calls_heat_mode(
    hass: HomeAssistant,
    device: MagicMock,
    config_entry: MagicMock,
) -> None:
    """Test controlling the entity through service calls."""

    device.system_mode = "heat"

    await init_integration(hass, config_entry)
    entity_id = f"climate.{device.name}"

    async_fire_time_changed(
        hass,
        utcnow() + SCAN_INTERVAL,
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.SET_TEMPERATURE,
        {TargetKey.ENTITY_ID: entity_id, ClimateServiceArgument.TEMPERATURE: 25},
        blocking=True,
    )
    device.set_hold_heat.assert_called_once_with(dt.time(2, 30), 25)
    device.set_hold_heat.reset_mock()

    device.set_hold_heat.side_effect = aiosomecomfort.SomeComfortError
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_TEMPERATURE,
            {TargetKey.ENTITY_ID: entity_id, ClimateServiceArgument.TEMPERATURE: 25},
            blocking=True,
        )
    device.set_hold_heat.assert_called_once_with(dt.time(2, 30), 25)
    device.set_hold_heat.reset_mock()
    assert exc_info.value.translation_key == "temp_failed_value"

    device.set_hold_heat.side_effect = aiosomecomfort.UnexpectedResponse
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_TEMPERATURE,
            {TargetKey.ENTITY_ID: entity_id, ClimateServiceArgument.TEMPERATURE: 25},
            blocking=True,
        )
    device.set_hold_heat.assert_called_once_with(dt.time(2, 30), 25)
    device.set_hold_heat.reset_mock()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.SET_TEMPERATURE,
        {
            TargetKey.ENTITY_ID: entity_id,
            ClimateServiceArgument.TARGET_TEMP_LOW: 25.0,
            ClimateServiceArgument.TARGET_TEMP_HIGH: 35.0,
        },
        blocking=True,
    )
    device.set_setpoint_cool.assert_called_with(35)
    device.set_setpoint_heat.assert_called_with(25)

    device.set_setpoint_heat.reset_mock()
    device.set_setpoint_heat.side_effect = aiosomecomfort.SomeComfortError
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_TEMPERATURE,
            {
                TargetKey.ENTITY_ID: entity_id,
                ClimateServiceArgument.TARGET_TEMP_LOW: 25.0,
                ClimateServiceArgument.TARGET_TEMP_HIGH: 35.0,
            },
            blocking=True,
        )
    device.set_setpoint_cool.assert_called_with(35)
    device.set_setpoint_heat.assert_called_with(25)
    assert exc_info.value.translation_key == "temp_failed_value"

    reset_mock(device)
    device.raw_ui_data["StatusHeat"] = 2
    device.raw_ui_data["StatusCool"] = 2

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_PRESET_MODE,
            {
                TargetKey.ENTITY_ID: entity_id,
                ClimateServiceArgument.PRESET_MODE: PRESET_HOLD,
            },
            blocking=True,
        )

    device.set_hold_heat.assert_called_once_with(True)
    device.set_hold_cool.assert_not_called()

    device.hold_heat = True
    device.hold_cool = True

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_TEMPERATURE,
            {TargetKey.ENTITY_ID: entity_id, ClimateServiceArgument.TEMPERATURE: "20"},
            blocking=True,
        )

    device.set_setpoint_heat.assert_called_once()

    reset_mock(device)

    device.set_hold_heat.side_effect = aiosomecomfort.SomeComfortError

    device.raw_ui_data["StatusHeat"] = 2
    device.raw_ui_data["StatusCool"] = 2

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_PRESET_MODE,
            {
                TargetKey.ENTITY_ID: entity_id,
                ClimateServiceArgument.PRESET_MODE: PRESET_HOLD,
            },
            blocking=True,
        )
    device.set_hold_heat.assert_called_once_with(True)
    device.set_hold_cool.assert_not_called()
    assert exc_info.value.translation_key == "set_hold_failed"

    reset_mock(device)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_PRESET_MODE,
            {
                TargetKey.ENTITY_ID: entity_id,
                ClimateServiceArgument.PRESET_MODE: PRESET_AWAY,
            },
            blocking=True,
        )

    device.set_hold_heat.assert_called_once_with(True, 22)
    device.set_hold_cool.assert_not_called()
    device.set_setpoint_cool.assert_not_called()

    reset_mock(device)

    device.set_hold_heat.side_effect = aiosomecomfort.SomeComfortError

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_PRESET_MODE,
            {
                TargetKey.ENTITY_ID: entity_id,
                ClimateServiceArgument.PRESET_MODE: PRESET_AWAY,
            },
            blocking=True,
        )

    device.set_hold_heat.assert_called_once_with(True, 22)
    device.set_hold_cool.assert_not_called()
    device.set_setpoint_cool.assert_not_called()
    assert exc_info.value.translation_key == "temp_failed_range"

    device.set_hold_heat.side_effect = aiosomecomfort.UnexpectedResponse

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_PRESET_MODE,
            {
                TargetKey.ENTITY_ID: entity_id,
                ClimateServiceArgument.PRESET_MODE: PRESET_AWAY,
            },
            blocking=True,
        )

    reset_mock(device)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_PRESET_MODE,
            {
                TargetKey.ENTITY_ID: entity_id,
                ClimateServiceArgument.PRESET_MODE: PRESET_NONE,
            },
            blocking=True,
        )

    device.set_hold_heat.assert_called_once_with(False)
    device.set_hold_cool.assert_called_once_with(False)

    device.set_hold_heat.reset_mock()
    device.set_hold_cool.reset_mock()
    device.set_hold_heat.side_effect = aiosomecomfort.SomeComfortError
    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_PRESET_MODE,
            {
                TargetKey.ENTITY_ID: entity_id,
                ClimateServiceArgument.PRESET_MODE: PRESET_NONE,
            },
            blocking=True,
        )

    device.set_hold_heat.assert_called_once_with(False)
    assert exc_info.value.translation_key == "stop_hold_failed"

    reset_mock(device)
    device.raw_ui_data["StatusHeat"] = 2
    device.raw_ui_data["StatusCool"] = 2

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_PRESET_MODE,
            {
                TargetKey.ENTITY_ID: entity_id,
                ClimateServiceArgument.PRESET_MODE: PRESET_HOLD,
            },
            blocking=True,
        )

    device.set_hold_heat.assert_called_once_with(True)
    device.set_hold_cool.assert_not_called()

    reset_mock(device)
    device.set_hold_heat.side_effect = aiosomecomfort.SomeComfortError

    device.raw_ui_data["StatusHeat"] = 2
    device.raw_ui_data["StatusCool"] = 2

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_PRESET_MODE,
            {
                TargetKey.ENTITY_ID: entity_id,
                ClimateServiceArgument.PRESET_MODE: PRESET_HOLD,
            },
            blocking=True,
        )

    device.set_hold_heat.assert_called_once_with(True)
    device.set_hold_cool.assert_not_called()

    reset_mock(device)


async def test_service_calls_auto_mode(
    hass: HomeAssistant,
    device: MagicMock,
    config_entry: MagicMock,
) -> None:
    """Test controlling the entity through service calls."""

    device.system_mode = "auto"

    await init_integration(hass, config_entry)
    entity_id = f"climate.{device.name}"

    async_fire_time_changed(
        hass,
        utcnow() + SCAN_INTERVAL,
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.SET_TEMPERATURE,
        {TargetKey.ENTITY_ID: entity_id, ClimateServiceArgument.TEMPERATURE: 15},
        blocking=True,
    )
    device.set_setpoint_cool.assert_not_called()
    device.set_setpoint_heat.assert_not_called()

    reset_mock(device)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.SET_TEMPERATURE,
        {
            TargetKey.ENTITY_ID: entity_id,
            ClimateServiceArgument.TARGET_TEMP_LOW: 25.0,
            ClimateServiceArgument.TARGET_TEMP_HIGH: 35.0,
        },
        blocking=True,
    )
    device.set_setpoint_cool.assert_called_once_with(35)
    device.set_setpoint_heat.assert_called_once_with(25)

    reset_mock(device)

    device.set_hold_cool.side_effect = aiosomecomfort.SomeComfortError
    device.set_hold_heat.side_effect = aiosomecomfort.SomeComfortError
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_TEMPERATURE,
            {TargetKey.ENTITY_ID: entity_id, ClimateServiceArgument.TEMPERATURE: 15},
            blocking=True,
        )
    device.set_setpoint_heat.assert_not_called()
    assert exc_info.value.translation_key == "temp_failed_value"

    reset_mock(device)

    device.set_setpoint_heat.side_effect = aiosomecomfort.SomeComfortError
    device.set_setpoint_cool.side_effect = aiosomecomfort.SomeComfortError
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_TEMPERATURE,
            {
                TargetKey.ENTITY_ID: entity_id,
                ClimateServiceArgument.TARGET_TEMP_LOW: 25.0,
                ClimateServiceArgument.TARGET_TEMP_HIGH: 35.0,
            },
            blocking=True,
        )
    device.set_setpoint_heat.assert_not_called()
    assert exc_info.value.translation_key == "temp_failed_value"

    reset_mock(device)

    device.set_hold_heat.side_effect = None
    device.set_hold_cool.side_effect = None

    device.raw_ui_data["StatusHeat"] = 2
    device.raw_ui_data["StatusCool"] = 2

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.SET_PRESET_MODE,
        {
            TargetKey.ENTITY_ID: entity_id,
            ClimateServiceArgument.PRESET_MODE: PRESET_HOLD,
        },
        blocking=True,
    )

    device.set_hold_cool.assert_called_once_with(True)
    device.set_hold_heat.assert_called_once_with(True)

    reset_mock(device)

    device.set_hold_heat.side_effect = aiosomecomfort.SomeComfortError
    device.raw_ui_data["StatusHeat"] = 2
    device.raw_ui_data["StatusCool"] = 2

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_PRESET_MODE,
            {
                TargetKey.ENTITY_ID: entity_id,
                ClimateServiceArgument.PRESET_MODE: PRESET_HOLD,
            },
            blocking=True,
        )
    device.set_hold_cool.assert_called_once_with(True)
    device.set_hold_heat.assert_called_once_with(True)
    assert exc_info.value.translation_key == "set_hold_failed"

    reset_mock(device)
    device.set_setpoint_heat.side_effect = None
    device.set_setpoint_cool.side_effect = None

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_PRESET_MODE,
            {
                TargetKey.ENTITY_ID: entity_id,
                ClimateServiceArgument.PRESET_MODE: PRESET_AWAY,
            },
            blocking=True,
        )

    device.set_hold_cool.assert_called_once_with(True, 12)
    device.set_hold_heat.assert_called_once_with(True, 22)

    reset_mock(device)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_PRESET_MODE,
            {
                TargetKey.ENTITY_ID: entity_id,
                ClimateServiceArgument.PRESET_MODE: PRESET_NONE,
            },
            blocking=True,
        )

    device.set_hold_heat.assert_called_once_with(False)
    device.set_hold_cool.assert_called_once_with(False)

    reset_mock(device)
    device.set_hold_cool.side_effect = aiosomecomfort.SomeComfortError
    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_PRESET_MODE,
            {
                TargetKey.ENTITY_ID: entity_id,
                ClimateServiceArgument.PRESET_MODE: PRESET_NONE,
            },
            blocking=True,
        )

    device.set_hold_heat.assert_not_called()
    device.set_hold_cool.assert_called_once_with(False)
    assert exc_info.value.translation_key == "stop_hold_failed"

    reset_mock(device)

    device.raw_ui_data["StatusHeat"] = 2
    device.raw_ui_data["StatusCool"] = 2

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_PRESET_MODE,
            {
                TargetKey.ENTITY_ID: entity_id,
                ClimateServiceArgument.PRESET_MODE: PRESET_HOLD,
            },
            blocking=True,
        )

    device.set_hold_cool.assert_called_once_with(True)
    device.set_hold_heat.assert_not_called()

    reset_mock(device)

    device.set_hold_cool.side_effect = aiosomecomfort.SomeComfortError
    device.raw_ui_data["StatusHeat"] = 2
    device.raw_ui_data["StatusCool"] = 2

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            ClimateService.SET_PRESET_MODE,
            {
                TargetKey.ENTITY_ID: entity_id,
                ClimateServiceArgument.PRESET_MODE: PRESET_HOLD,
            },
            blocking=True,
        )

    device.set_hold_cool.assert_called_once_with(True)
    device.set_hold_heat.assert_not_called()
    assert exc_info.value.translation_key == "set_hold_failed"


async def test_async_update_errors(
    hass: HomeAssistant,
    device: MagicMock,
    config_entry: MagicMock,
    client: MagicMock,
) -> None:
    """Test update with errors."""

    await init_integration(hass, config_entry)

    device.refresh.side_effect = aiosomecomfort.UnauthorizedError
    client.login.side_effect = aiosomecomfort.AuthError
    entity_id = f"climate.{device.name}"
    state = hass.states.get(entity_id)
    assert state.state == "off"

    # Due to server instability, only mark entity unavailable after RETRY update
    # attempts
    for _ in range(RETRY):
        async_fire_time_changed(
            hass,
            utcnow() + SCAN_INTERVAL,
        )
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state.state == "off"

    async_fire_time_changed(
        hass,
        utcnow() + SCAN_INTERVAL,
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == "unavailable"

    reset_mock(device)
    device.refresh.side_effect = None
    client.login.side_effect = None

    async_fire_time_changed(
        hass,
        utcnow() + SCAN_INTERVAL,
    )
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == "off"

    device.refresh.side_effect = aiosomecomfort.UnexpectedResponse
    client.login.side_effect = None
    async_fire_time_changed(
        hass,
        utcnow() + SCAN_INTERVAL,
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == "off"

    device.refresh.side_effect = [aiosomecomfort.UnauthorizedError, None]
    client.login.side_effect = None
    async_fire_time_changed(
        hass,
        utcnow() + SCAN_INTERVAL,
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == "off"

    device.refresh.side_effect = aiosomecomfort.SomeComfortError
    client.login.side_effect = aiosomecomfort.AuthError
    async_fire_time_changed(
        hass,
        utcnow() + SCAN_INTERVAL,
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == "off"

    device.refresh.side_effect = ClientConnectionError

    # Due to server instability, only mark entity unavailable after RETRY update
    # attempts
    for _ in range(RETRY):
        async_fire_time_changed(
            hass,
            utcnow() + SCAN_INTERVAL,
        )
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state.state == "off"

    async_fire_time_changed(
        hass,
        utcnow() + SCAN_INTERVAL,
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == "unavailable"


async def test_unique_id(
    hass: HomeAssistant,
    device: MagicMock,
    config_entry: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test unique id convert to string."""
    config_entry.add_to_hass(hass)
    entity_registry.async_get_or_create(
        Platform.CLIMATE,
        DOMAIN,
        device.deviceid,
        config_entry=config_entry,
        suggested_object_id=device.name,
    )
    await init_integration(hass, config_entry)
    entity_entry = entity_registry.async_get(f"climate.{device.name}")
    assert entity_entry.unique_id == str(device.deviceid)


async def test_preset_mode(
    hass: HomeAssistant,
    device: MagicMock,
    config_entry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test mode settings properly reflected."""
    await init_integration(hass, config_entry)
    entity_id = f"climate.{device.name}"

    device.raw_ui_data["StatusHeat"] = 3
    device.raw_ui_data["StatusCool"] = 3

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_NONE

    device.raw_ui_data["StatusHeat"] = MODE_TEMPORARY_HOLD
    device.raw_ui_data["StatusCool"] = MODE_TEMPORARY_HOLD

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_HOLD

    device.raw_ui_data["StatusHeat"] = MODE_PERMANENT_HOLD
    device.raw_ui_data["StatusCool"] = MODE_PERMANENT_HOLD

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_HOLD

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.SET_PRESET_MODE,
        {
            TargetKey.ENTITY_ID: entity_id,
            ClimateServiceArgument.PRESET_MODE: PRESET_AWAY,
        },
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_AWAY

    device.raw_ui_data["StatusHeat"] = 3
    device.raw_ui_data["StatusCool"] = 3
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_NONE


@pytest.mark.parametrize(
    ("system_mode", "temperature_unit", "service_data", "heat_calls", "cool_calls"),
    [
        pytest.param(
            "heat",
            "C",
            {
                HoneywellServiceArgument.UNTIL: "22:30:00",
                HoneywellServiceArgument.TEMPERATURE: 22,
            },
            [call(dt.time(22, 30), 22)],
            [],
            id="heat",
        ),
        pytest.param(
            "emheat",
            "C",
            {
                HoneywellServiceArgument.UNTIL: "22:30:00",
                HoneywellServiceArgument.TEMPERATURE: 22,
            },
            [call(dt.time(22, 30), 22)],
            [],
            id="emheat",
        ),
        pytest.param(
            "cool",
            "C",
            {
                HoneywellServiceArgument.UNTIL: "22:30:00",
                HoneywellServiceArgument.TEMPERATURE: 18,
            },
            [],
            [call(dt.time(22, 30), 18)],
            id="cool",
        ),
        pytest.param(
            "heat",
            "C",
            {HoneywellServiceArgument.UNTIL: "22:30:00"},
            [call(dt.time(22, 30), None)],
            [],
            id="heat_without_temperature",
        ),
        pytest.param(
            "cool",
            "C",
            {HoneywellServiceArgument.UNTIL: "22:30:00"},
            [],
            [call(dt.time(22, 30), None)],
            id="cool_without_temperature",
        ),
        pytest.param(
            "auto",
            "C",
            {HoneywellServiceArgument.UNTIL: "22:30:00"},
            [call(dt.time(22, 30), None)],
            [call(dt.time(22, 30), None)],
            id="auto_without_temperature",
        ),
        pytest.param(
            "heat",
            "C",
            {HoneywellServiceArgument.UNTIL: "00:00:00"},
            [call(dt.time(0, 0), None)],
            [],
            id="midnight",
        ),
        pytest.param(
            "heat",
            "F",
            {
                HoneywellServiceArgument.UNTIL: "22:30:00",
                HoneywellServiceArgument.TEMPERATURE: -5,
            },
            [call(dt.time(22, 30), 23)],
            [],
            id="temperature_converted",
        ),
        pytest.param(
            "heat",
            "F",
            {
                HoneywellServiceArgument.UNTIL: "22:30:00",
                HoneywellServiceArgument.TEMPERATURE: 1.7,
            },
            [call(dt.time(22, 30), 35)],
            [],
            id="rounded_limit_clamped",
        ),
    ],
)
async def test_set_hold_until(
    hass: HomeAssistant,
    device: MagicMock,
    config_entry: MockConfigEntry,
    system_mode: str,
    temperature_unit: str,
    service_data: dict[str, str | float],
    heat_calls: list[_Call],
    cool_calls: list[_Call],
) -> None:
    """Test setting a temporary hold until a given time."""
    device.system_mode = system_mode
    device.temperature_unit = temperature_unit
    await init_integration(hass, config_entry)

    await hass.services.async_call(
        DOMAIN,
        HoneywellService.SET_HOLD_UNTIL,
        {TargetKey.ENTITY_ID: ENTITY_ID, **service_data},
        blocking=True,
    )

    assert device.set_hold_heat.mock_calls == heat_calls
    assert device.set_hold_cool.mock_calls == cool_calls


@pytest.mark.parametrize(
    (
        "system_mode",
        "temperature_unit",
        "service_data",
        "translation_key",
        "translation_placeholders",
    ),
    [
        pytest.param(
            "heat",
            "C",
            {HoneywellServiceArgument.UNTIL: "22:40:00"},
            "hold_until_invalid_time",
            None,
            id="not_on_quarter_hour",
        ),
        pytest.param(
            "heat",
            "C",
            {HoneywellServiceArgument.UNTIL: "22:30:10"},
            "hold_until_invalid_time",
            None,
            id="seconds",
        ),
        pytest.param(
            "off",
            "C",
            {HoneywellServiceArgument.UNTIL: "22:30:00"},
            "hold_until_invalid_mode",
            {"mode": "off"},
            id="system_off",
        ),
        pytest.param(
            "auto",
            "C",
            {
                HoneywellServiceArgument.UNTIL: "22:30:00",
                HoneywellServiceArgument.TEMPERATURE: 20,
            },
            "hold_until_temperature_mode",
            {"mode": "auto"},
            id="temperature_in_auto",
        ),
        pytest.param(
            "heat",
            "C",
            {
                HoneywellServiceArgument.UNTIL: "22:30:00",
                HoneywellServiceArgument.TEMPERATURE: 36,
            },
            "hold_until_invalid_temperature",
            {"temperature": "36.0", "min_temp": "20", "max_temp": "35"},
            id="heat_temperature_too_high",
        ),
        pytest.param(
            "heat",
            "C",
            {
                HoneywellServiceArgument.UNTIL: "22:30:00",
                HoneywellServiceArgument.TEMPERATURE: 19,
            },
            "hold_until_invalid_temperature",
            {"temperature": "19.0", "min_temp": "20", "max_temp": "35"},
            id="heat_temperature_too_low",
        ),
        pytest.param(
            "cool",
            "C",
            {
                HoneywellServiceArgument.UNTIL: "22:30:00",
                HoneywellServiceArgument.TEMPERATURE: 21,
            },
            "hold_until_invalid_temperature",
            {"temperature": "21.0", "min_temp": "10", "max_temp": "20"},
            id="cool_temperature_too_high",
        ),
        pytest.param(
            "heat",
            "F",
            {
                HoneywellServiceArgument.UNTIL: "22:30:00",
                HoneywellServiceArgument.TEMPERATURE: 2,
            },
            "hold_until_invalid_temperature",
            {"temperature": "2.0", "min_temp": "-6.7", "max_temp": "1.7"},
            id="temperature_range_in_configured_unit",
        ),
    ],
)
async def test_set_hold_until_invalid(
    hass: HomeAssistant,
    device: MagicMock,
    config_entry: MockConfigEntry,
    system_mode: str,
    temperature_unit: str,
    service_data: dict[str, str | float],
    translation_key: str,
    translation_placeholders: dict[str, str] | None,
) -> None:
    """Test a temporary hold is not set with invalid input."""
    device.system_mode = system_mode
    device.temperature_unit = temperature_unit
    await init_integration(hass, config_entry)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            HoneywellService.SET_HOLD_UNTIL,
            {TargetKey.ENTITY_ID: ENTITY_ID, **service_data},
            blocking=True,
        )

    assert exc_info.value.translation_key == translation_key
    assert exc_info.value.translation_placeholders == translation_placeholders
    device.set_hold_heat.assert_not_called()
    device.set_hold_cool.assert_not_called()


@pytest.mark.parametrize(
    "service_data",
    [
        pytest.param({}, id="until_missing"),
        pytest.param({HoneywellServiceArgument.UNTIL: "noon"}, id="until_not_a_time"),
    ],
)
async def test_set_hold_until_invalid_schema(
    hass: HomeAssistant,
    device: MagicMock,
    config_entry: MockConfigEntry,
    service_data: dict[str, str],
) -> None:
    """Test a temporary hold is not set when the action data is rejected."""
    await init_integration(hass, config_entry)

    with pytest.raises(probatio.Invalid):
        await hass.services.async_call(
            DOMAIN,
            HoneywellService.SET_HOLD_UNTIL,
            {TargetKey.ENTITY_ID: ENTITY_ID, **service_data},
            blocking=True,
        )

    device.set_hold_heat.assert_not_called()
    device.set_hold_cool.assert_not_called()


@pytest.mark.parametrize(
    ("system_mode", "failing_call", "error"),
    [
        pytest.param(
            "heat", "set_hold_heat", aiosomecomfort.SomeComfortError, id="heat"
        ),
        pytest.param(
            "heat",
            "set_hold_heat",
            aiosomecomfort.ConnectionError,
            id="heat_connection_error",
        ),
        pytest.param(
            "heat",
            "set_hold_heat",
            aiosomecomfort.UnexpectedResponse,
            id="heat_unexpected_response",
        ),
        pytest.param(
            "cool", "set_hold_cool", aiosomecomfort.SomeComfortError, id="cool"
        ),
        pytest.param(
            "auto", "set_hold_heat", aiosomecomfort.SomeComfortError, id="auto_heat"
        ),
    ],
)
async def test_set_hold_until_failed(
    hass: HomeAssistant,
    device: MagicMock,
    config_entry: MockConfigEntry,
    system_mode: str,
    failing_call: str,
    error: type[Exception],
) -> None:
    """Test errors from the Honeywell API when setting a temporary hold."""
    device.system_mode = system_mode
    getattr(device, failing_call).side_effect = error
    await init_integration(hass, config_entry)

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            HoneywellService.SET_HOLD_UNTIL,
            {
                TargetKey.ENTITY_ID: ENTITY_ID,
                HoneywellServiceArgument.UNTIL: "22:30:00",
            },
            blocking=True,
        )

    assert exc_info.value.translation_key == "set_hold_until_failed"


@pytest.mark.parametrize(
    ("side_effect", "expectation", "preset_mode"),
    [
        pytest.param(None, does_not_raise(), PRESET_HOLD, id="hold_set"),
        pytest.param(
            aiosomecomfort.SomeComfortError,
            pytest.raises(HomeAssistantError),
            PRESET_AWAY,
            id="hold_failed",
        ),
    ],
)
async def test_set_hold_until_away_preset(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    device: MagicMock,
    config_entry: MockConfigEntry,
    side_effect: type[Exception] | None,
    expectation: AbstractContextManager,
    preset_mode: str,
) -> None:
    """Test a temporary hold replaces the away preset only when it is set."""
    device.system_mode = "heat"
    device.raw_ui_data["StatusHeat"] = MODE_PERMANENT_HOLD
    await init_integration(hass, config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.SET_PRESET_MODE,
        {
            TargetKey.ENTITY_ID: ENTITY_ID,
            ClimateServiceArgument.PRESET_MODE: PRESET_AWAY,
        },
        blocking=True,
    )
    assert hass.states.get(ENTITY_ID).attributes[ATTR_PRESET_MODE] == PRESET_AWAY

    device.set_hold_heat.side_effect = side_effect
    with expectation:
        await hass.services.async_call(
            DOMAIN,
            HoneywellService.SET_HOLD_UNTIL,
            {
                TargetKey.ENTITY_ID: ENTITY_ID,
                HoneywellServiceArgument.UNTIL: "22:30:00",
            },
            blocking=True,
        )

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).attributes[ATTR_PRESET_MODE] == preset_mode
