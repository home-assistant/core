"""Test the Whirlpool Sixth Sense climate domain."""
import datetime
from unittest.mock import MagicMock

import aiosomecomfort

from homeassistant.components.climate import (
    ATTR_AUX_HEAT,
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    DOMAIN as CLIMATE_DOMAIN,
    FAN_AUTO,
    FAN_DIFFUSE,
    FAN_ON,
    PRESET_AWAY,
    PRESET_NONE,
    SERVICE_SET_AUX_HEAT,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.components.honeywell.climate import SCAN_INTERVAL
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import utcnow

from . import init_integration, reset_mock

from tests.common import async_fire_time_changed

FAN_ACTION = "fan_action"
PRESET_HOLD = "Hold"


async def test_no_thermostats(
    hass: HomeAssistant, device: MagicMock, config_entry: MagicMock
) -> None:
    """Test the setup of the climate entities when there are no appliances available."""
    device._data = {}
    await init_integration(hass, config_entry)
    assert len(hass.states.async_all()) == 0


async def test_static_attributes(
    hass: HomeAssistant, device: MagicMock, config_entry: MagicMock
) -> None:
    """Test static climate attributes."""
    await init_integration(hass, config_entry)

    entity_id = f"climate.{device.name}"
    entry = er.async_get(hass).async_get(entity_id)
    assert entry

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == HVACMode.OFF

    attributes = state.attributes
    assert attributes[ATTR_FRIENDLY_NAME] == entity_id.split(".")[1]

    assert (
        attributes[ATTR_SUPPORTED_FEATURES]
        == ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.AUX_HEAT
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        | ClimateEntityFeature.TARGET_HUMIDITY
    )

    assert attributes[ATTR_HVAC_MODES] == [
        HVACMode.OFF,
        HVACMode.HEAT_COOL,
        HVACMode.COOL,
        HVACMode.HEAT,
    ]
    assert attributes[ATTR_PRESET_MODES] == [
        PRESET_NONE,
        PRESET_AWAY,
        PRESET_HOLD,
    ]
    assert attributes[ATTR_MIN_TEMP] == -13.9
    assert attributes[ATTR_MAX_TEMP] == 1.7
    assert attributes[ATTR_CURRENT_TEMPERATURE] == -6.7
    assert attributes[FAN_ACTION] == "idle"
    assert attributes["permanent_hold"] is False
    assert attributes["aux_heat"] == "off"


async def test_dynamic_attributes(
    hass: HomeAssistant, device: MagicMock, config_entry: MagicMock
) -> None:
    """Test dynamic attributes."""

    await init_integration(hass, config_entry)

    entity_id = f"climate.{device.name}"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == HVACMode.OFF
    attributes = state.attributes
    assert attributes["current_temperature"] == -6.7
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
    assert state is not None
    assert state.state == HVACMode.COOL
    attributes = state.attributes
    assert attributes["current_temperature"] == -6.1
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
    assert state is not None
    assert state.state == HVACMode.HEAT
    attributes = state.attributes
    assert attributes["current_temperature"] == 16.1
    assert attributes["current_humidity"] == 50

    device.system_mode = "auto"
    device.current_temperature = 61
    device.current_humidity = 50

    async_fire_time_changed(
        hass,
        utcnow() + SCAN_INTERVAL,
    )
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == HVACMode.HEAT_COOL


async def test_mode_service_calls(
    hass: HomeAssistant, device: MagicMock, config_entry: MagicMock
) -> None:
    """Test controlling the entity mode through service calls."""
    await init_integration(hass, config_entry)
    entity_id = f"climate.{device.name}"

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    device.set_system_mode.assert_called_once_with("off")

    device.set_system_mode.reset_mock()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    device.set_system_mode.assert_called_once_with("auto")

    device.set_system_mode.reset_mock()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVACMode.COOL},
        blocking=True,
    )
    device.set_system_mode.assert_called_once_with("cool")

    device.set_system_mode.reset_mock()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )
    device.set_system_mode.assert_called_once_with("heat")

    device.set_system_mode.reset_mock()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVACMode.HEAT_COOL},
        blocking=True,
    )
    device.set_system_mode.assert_called_once_with("auto")


async def test_auxheat_service_calls(
    hass: HomeAssistant, device: MagicMock, config_entry: MagicMock
) -> None:
    """Test controlling the auxheat through service calls."""
    await init_integration(hass, config_entry)
    entity_id = f"climate.{device.name}"

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_AUX_HEAT,
        {ATTR_ENTITY_ID: entity_id, ATTR_AUX_HEAT: True},
        blocking=True,
    )
    device.set_system_mode.assert_called_once_with("emheat")

    device.set_system_mode.reset_mock()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_AUX_HEAT,
        {ATTR_ENTITY_ID: entity_id, ATTR_AUX_HEAT: False},
        blocking=True,
    )
    device.set_system_mode.assert_called_once_with("heat")


async def test_fan_modes_service_calls(
    hass: HomeAssistant, device: MagicMock, config_entry: MagicMock
) -> None:
    """Test controlling the fan modes through service calls."""
    await init_integration(hass, config_entry)
    entity_id = f"climate.{device.name}"

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_FAN_MODE: FAN_AUTO},
        blocking=True,
    )

    device.set_fan_mode.assert_called_once_with("auto")

    device.set_fan_mode.reset_mock()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_FAN_MODE: FAN_ON},
        blocking=True,
    )

    device.set_fan_mode.assert_called_once_with("on")

    device.set_fan_mode.reset_mock()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_FAN_MODE: FAN_DIFFUSE},
        blocking=True,
    )

    device.set_fan_mode.assert_called_once_with("circulate")


async def test_service_calls_off_mode(
    hass: HomeAssistant, device: MagicMock, config_entry: MagicMock
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
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 15},
        blocking=True,
    )

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_TARGET_TEMP_LOW: 25.0,
            ATTR_TARGET_TEMP_HIGH: 35.0,
        },
        blocking=True,
    )
    device.set_setpoint_cool.assert_called_with(95)
    device.set_setpoint_heat.assert_called_with(77)

    device.set_setpoint_heat.reset_mock()
    device.set_setpoint_heat.side_effect = aiosomecomfort.SomeComfortError
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_TARGET_TEMP_LOW: 25.0,
            ATTR_TARGET_TEMP_HIGH: 35.0,
        },
        blocking=True,
    )
    device.set_setpoint_cool.assert_called_with(95)
    device.set_setpoint_heat.assert_called_with(77)

    reset_mock(device)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 15},
        blocking=True,
    )
    device.set_setpoint_heat.assert_not_called()
    device.set_setpoint_cool.assert_not_called()

    reset_mock(device)
    device.raw_ui_data["StatusHeat"] = 2
    device.raw_ui_data["StatusCool"] = 2

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_HOLD},
        blocking=True,
    )

    device.set_hold_cool.assert_not_called()
    device.set_hold_heat.assert_not_called()

    reset_mock(device)
    device.set_setpoint_heat.side_effect = aiosomecomfort.SomeComfortError

    device.raw_ui_data["StatusHeat"] = 2
    device.raw_ui_data["StatusCool"] = 2

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_HOLD},
        blocking=True,
    )
    device.set_hold_cool.assert_not_called()
    device.set_hold_heat.assert_not_called()

    reset_mock(device)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_AWAY},
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
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_NONE},
        blocking=True,
    )

    device.set_hold_heat.assert_called_once_with(False)
    device.set_hold_cool.assert_called_once_with(False)

    reset_mock(device)
    device.set_hold_cool.side_effect = aiosomecomfort.SomeComfortError

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_NONE},
        blocking=True,
    )

    device.set_hold_heat.assert_not_called()
    device.set_hold_cool.assert_called_once_with(False)

    reset_mock(device)
    device.raw_ui_data["StatusHeat"] = 2
    device.raw_ui_data["StatusCool"] = 2

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_HOLD},
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
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_HOLD},
        blocking=True,
    )

    device.set_hold_heat.assert_not_called()
    device.set_hold_cool.assert_not_called()


async def test_service_calls_cool_mode(
    hass: HomeAssistant, device: MagicMock, config_entry: MagicMock
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
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 15},
        blocking=True,
    )
    device.set_hold_cool.assert_called_once_with(datetime.time(2, 30), 59)
    device.set_hold_cool.reset_mock()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_TARGET_TEMP_LOW: 25.0,
            ATTR_TARGET_TEMP_HIGH: 35.0,
        },
        blocking=True,
    )
    device.set_setpoint_cool.assert_called_with(95)
    device.set_setpoint_heat.assert_called_with(77)

    device.set_setpoint_cool.reset_mock()
    device.set_setpoint_cool.side_effect = aiosomecomfort.SomeComfortError
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_TARGET_TEMP_LOW: 25.0,
            ATTR_TARGET_TEMP_HIGH: 35.0,
        },
        blocking=True,
    )
    device.set_setpoint_cool.assert_called_with(95)
    device.set_setpoint_heat.assert_called_with(77)

    reset_mock(device)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_AWAY},
        blocking=True,
    )

    device.set_hold_cool.assert_called_once_with(True, 12)
    device.set_hold_heat.assert_not_called()
    device.set_setpoint_heat.assert_not_called()

    reset_mock(device)
    device.set_setpoint_cool.side_effect = aiosomecomfort.SomeComfortError

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_AWAY},
        blocking=True,
    )

    device.set_hold_cool.assert_called_once_with(True, 12)
    device.set_hold_heat.assert_not_called()
    device.set_setpoint_heat.assert_not_called()

    reset_mock(device)
    device.raw_ui_data["StatusHeat"] = 2
    device.raw_ui_data["StatusCool"] = 2

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_HOLD},
        blocking=True,
    )

    device.set_hold_cool.assert_called_once_with(True)
    device.set_hold_heat.assert_not_called()

    device.hold_heat = True
    device.hold_cool = True

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: "20"},
        blocking=True,
    )

    device.set_setpoint_cool.assert_called_once()

    reset_mock(device)
    device.set_setpoint_cool.side_effect = aiosomecomfort.SomeComfortError

    device.raw_ui_data["StatusHeat"] = 2
    device.raw_ui_data["StatusCool"] = 2

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_HOLD},
        blocking=True,
    )
    device.set_hold_cool.assert_called_once_with(True)
    device.set_hold_heat.assert_not_called()

    reset_mock(device)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_NONE},
        blocking=True,
    )

    device.set_hold_heat.assert_called_once_with(False)
    device.set_hold_cool.assert_called_once_with(False)

    reset_mock(device)
    device.set_hold_cool.side_effect = aiosomecomfort.SomeComfortError

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_NONE},
        blocking=True,
    )

    device.set_hold_heat.assert_not_called()
    device.set_hold_cool.assert_called_once_with(False)

    reset_mock(device)
    device.raw_ui_data["StatusHeat"] = 2
    device.raw_ui_data["StatusCool"] = 2

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_HOLD},
        blocking=True,
    )

    device.set_hold_cool.assert_called_once_with(True)
    device.set_hold_heat.assert_not_called()

    reset_mock(device)
    device.set_hold_cool.side_effect = aiosomecomfort.SomeComfortError

    device.raw_ui_data["StatusHeat"] = 2
    device.raw_ui_data["StatusCool"] = 2

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_HOLD},
        blocking=True,
    )

    device.set_hold_cool.assert_called_once_with(True)
    device.set_hold_heat.assert_not_called()


async def test_service_calls_heat_mode(
    hass: HomeAssistant, device: MagicMock, config_entry: MagicMock
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
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 15},
        blocking=True,
    )
    device.set_hold_heat.assert_called_once_with(datetime.time(2, 30), 59)
    device.set_hold_heat.reset_mock()

    device.set_setpoint_heat.side_effect = aiosomecomfort.SomeComfortError

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 15},
        blocking=True,
    )
    device.set_hold_heat.assert_called_once_with(datetime.time(2, 30), 59)
    device.set_hold_heat.reset_mock()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_TARGET_TEMP_LOW: 25.0,
            ATTR_TARGET_TEMP_HIGH: 35.0,
        },
        blocking=True,
    )
    device.set_setpoint_cool.assert_called_with(95)
    device.set_setpoint_heat.assert_called_with(77)

    device.set_setpoint_heat.reset_mock()
    device.set_setpoint_heat.side_effect = aiosomecomfort.SomeComfortError
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_TARGET_TEMP_LOW: 25.0,
            ATTR_TARGET_TEMP_HIGH: 35.0,
        },
        blocking=True,
    )
    device.set_setpoint_cool.assert_called_with(95)
    device.set_setpoint_heat.assert_called_with(77)

    reset_mock(device)
    device.raw_ui_data["StatusHeat"] = 2
    device.raw_ui_data["StatusCool"] = 2

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_HOLD},
        blocking=True,
    )

    device.set_hold_heat.assert_called_once_with(True)
    device.set_hold_cool.assert_not_called()

    device.hold_heat = True
    device.hold_cool = True

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: "20"},
        blocking=True,
    )

    device.set_setpoint_heat.assert_called_once()

    reset_mock(device)
    device.set_setpoint_heat.side_effect = aiosomecomfort.SomeComfortError

    device.raw_ui_data["StatusHeat"] = 2
    device.raw_ui_data["StatusCool"] = 2

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_HOLD},
        blocking=True,
    )
    device.set_hold_heat.assert_called_once_with(True)
    device.set_hold_cool.assert_not_called()

    reset_mock(device)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_AWAY},
        blocking=True,
    )

    device.set_hold_heat.assert_called_once_with(True, 22)
    device.set_hold_cool.assert_not_called()
    device.set_setpoint_cool.assert_not_called()

    reset_mock(device)
    device.set_setpoint_heat.side_effect = aiosomecomfort.SomeComfortError

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_AWAY},
        blocking=True,
    )

    device.set_hold_heat.assert_called_once_with(True, 22)
    device.set_hold_cool.assert_not_called()
    device.set_setpoint_cool.assert_not_called()

    reset_mock(device)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_NONE},
        blocking=True,
    )

    device.set_hold_heat.assert_called_once_with(False)
    device.set_hold_cool.assert_called_once_with(False)

    device.set_hold_heat.reset_mock()
    device.set_hold_cool.reset_mock()
    device.set_hold_heat.side_effect = aiosomecomfort.SomeComfortError

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_NONE},
        blocking=True,
    )

    device.set_hold_heat.assert_called_once_with(False)

    reset_mock(device)
    device.raw_ui_data["StatusHeat"] = 2
    device.raw_ui_data["StatusCool"] = 2

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_HOLD},
        blocking=True,
    )

    device.set_hold_heat.assert_called_once_with(True)
    device.set_hold_cool.assert_not_called()

    reset_mock(device)
    device.set_hold_heat.side_effect = aiosomecomfort.SomeComfortError

    device.raw_ui_data["StatusHeat"] = 2
    device.raw_ui_data["StatusCool"] = 2

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_HOLD},
        blocking=True,
    )

    device.set_hold_heat.assert_called_once_with(True)
    device.set_hold_cool.assert_not_called()

    reset_mock(device)


async def test_service_calls_auto_mode(
    hass: HomeAssistant, device: MagicMock, config_entry: MagicMock
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
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 15},
        blocking=True,
    )
    device.set_setpoint_cool.assert_not_called()
    device.set_setpoint_heat.assert_not_called()

    device.set_setpoint_cool.reset_mock()
    device.set_setpoint_heat.reset_mock()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_TARGET_TEMP_LOW: 25.0,
            ATTR_TARGET_TEMP_HIGH: 35.0,
        },
        blocking=True,
    )
    device.set_setpoint_cool.assert_called_once_with(95)
    device.set_setpoint_heat.assert_called_once_with(77)

    device.set_setpoint_cool.reset_mock()
    device.set_setpoint_heat.reset_mock()
    device.set_setpoint_cool.side_effect = aiosomecomfort.SomeComfortError
    device.set_setpoint_heat.side_effect = aiosomecomfort.SomeComfortError

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 15},
        blocking=True,
    )
    device.set_setpoint_heat.assert_not_called()

    device.set_setpoint_heat.reset_mock()
    device.set_setpoint_cool.reset_mock()
    device.set_setpoint_heat.side_effect = aiosomecomfort.SomeComfortError
    device.set_setpoint_cool.side_effect = aiosomecomfort.SomeComfortError
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_TARGET_TEMP_LOW: 25.0,
            ATTR_TARGET_TEMP_HIGH: 35.0,
        },
        blocking=True,
    )
    device.set_setpoint_heat.assert_not_called()

    reset_mock(device)
    device.raw_ui_data["StatusHeat"] = 2
    device.raw_ui_data["StatusCool"] = 2

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_HOLD},
        blocking=True,
    )

    device.set_hold_cool.assert_called_once_with(True)
    device.set_hold_heat.assert_called_once_with(True)

    reset_mock(device)

    device.set_setpoint_heat.side_effect = aiosomecomfort.SomeComfortError
    device.raw_ui_data["StatusHeat"] = 2
    device.raw_ui_data["StatusCool"] = 2

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_HOLD},
        blocking=True,
    )
    device.set_hold_cool.assert_called_once_with(True)
    device.set_hold_heat.assert_called_once_with(True)

    reset_mock(device)
    device.set_setpoint_heat.side_effect = None
    device.set_setpoint_cool.side_effect = None

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_AWAY},
        blocking=True,
    )

    device.set_hold_cool.assert_called_once_with(True, 12)
    device.set_hold_heat.assert_called_once_with(True, 22)

    reset_mock(device)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_NONE},
        blocking=True,
    )

    device.set_hold_heat.assert_called_once_with(False)
    device.set_hold_cool.assert_called_once_with(False)

    reset_mock(device)
    device.set_hold_cool.side_effect = aiosomecomfort.SomeComfortError

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_NONE},
        blocking=True,
    )

    device.set_hold_heat.assert_not_called()
    device.set_hold_cool.assert_called_once_with(False)

    reset_mock(device)
    device.raw_ui_data["StatusHeat"] = 2
    device.raw_ui_data["StatusCool"] = 2

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_HOLD},
        blocking=True,
    )

    device.set_hold_cool.assert_called_once_with(True)
    device.set_hold_heat.assert_not_called()

    reset_mock(device)
    device.set_hold_cool.side_effect = aiosomecomfort.SomeComfortError
    device.raw_ui_data["StatusHeat"] = 2
    device.raw_ui_data["StatusCool"] = 2

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_HOLD},
        blocking=True,
    )

    device.set_hold_cool.assert_called_once_with(True)
    device.set_hold_heat.assert_not_called()


async def test_async_update_errors(
    hass: HomeAssistant,
    device: MagicMock,
    config_entry: MagicMock,
    client: MagicMock,
) -> None:
    """Test update with errors."""

    await init_integration(hass, config_entry)

    device.refresh.side_effect = aiosomecomfort.SomeComfortError
    client.login.side_effect = aiosomecomfort.SomeComfortError
    async_fire_time_changed(
        hass,
        utcnow() + SCAN_INTERVAL,
    )
    await hass.async_block_till_done()

    client.login.assert_called()


async def test_aux_heat_off_service_call(
    hass: HomeAssistant, device: MagicMock, config_entry: MagicMock
) -> None:
    """Test aux heat off turns of system when no heat configured."""
    device.raw_ui_data["SwitchHeatAllowed"] = False
    device.raw_ui_data["SwitchAutoAllowed"] = False
    device.raw_ui_data["SwitchEmergencyHeatAllowed"] = True

    await init_integration(hass, config_entry)

    entity_id = f"climate.{device.name}"
    entry = er.async_get(hass).async_get(entity_id)
    assert entry

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == HVACMode.OFF

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_AUX_HEAT,
        {ATTR_ENTITY_ID: entity_id, ATTR_AUX_HEAT: False},
        blocking=True,
    )
    device.set_system_mode.assert_called_once_with("off")
