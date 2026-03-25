"""Tests for the Aprilaire climate entity."""

from unittest.mock import MagicMock

from pyaprilaire.const import Attribute

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HUMIDITY,
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    DOMAIN as CLIMATE_DOMAIN,
    FAN_AUTO,
    FAN_ON,
    PRESET_AWAY,
    PRESET_NONE,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

from .conftest import setup_integration

ENTITY_ID = "climate.test_thermostat"


async def test_climate_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
) -> None:
    """Test climate entity state in auto mode."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.AUTO
    assert state.attributes["current_temperature"] == 22.5
    assert state.attributes["current_humidity"] == 45
    assert state.attributes["target_temp_high"] == 25.0
    assert state.attributes["target_temp_low"] == 20.0
    assert state.attributes["humidity"] == 35
    assert state.attributes["fan_mode"] == FAN_AUTO
    assert state.attributes["preset_mode"] == PRESET_NONE
    assert state.attributes["hvac_action"] == HVACAction.IDLE


async def test_climate_hvac_modes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
) -> None:
    """Test supported HVAC modes with thermostat_modes=5."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert HVACMode.OFF in state.attributes["hvac_modes"]
    assert HVACMode.HEAT in state.attributes["hvac_modes"]
    assert HVACMode.COOL in state.attributes["hvac_modes"]
    assert HVACMode.AUTO in state.attributes["hvac_modes"]


async def test_climate_supported_features_auto_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
) -> None:
    """Test supported features in auto mode (mode=5)."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    features = state.attributes["supported_features"]
    assert features & ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
    assert features & ClimateEntityFeature.TARGET_HUMIDITY
    assert features & ClimateEntityFeature.PRESET_MODE
    assert features & ClimateEntityFeature.FAN_MODE


async def test_climate_supported_features_heat_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
    base_coordinator_data: dict,
) -> None:
    """Test supported features in heat mode (non-auto)."""
    base_coordinator_data[Attribute.MODE] = 2
    base_coordinator_data[Attribute.HUMIDIFICATION_AVAILABLE] = 0
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    features = state.attributes["supported_features"]
    assert features & ClimateEntityFeature.TARGET_TEMPERATURE
    assert not (features & ClimateEntityFeature.TARGET_TEMPERATURE_RANGE)
    assert not (features & ClimateEntityFeature.TARGET_HUMIDITY)


async def test_climate_hvac_action_heating(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
    base_coordinator_data: dict,
) -> None:
    """Test HVAC action shows heating."""
    base_coordinator_data[Attribute.HEATING_EQUIPMENT_STATUS] = 1
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes["hvac_action"] == HVACAction.HEATING


async def test_climate_hvac_action_cooling(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
    base_coordinator_data: dict,
) -> None:
    """Test HVAC action shows cooling."""
    base_coordinator_data[Attribute.COOLING_EQUIPMENT_STATUS] = 1
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes["hvac_action"] == HVACAction.COOLING


async def test_climate_target_temperature_cool_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
    base_coordinator_data: dict,
) -> None:
    """Test target temperature returns cool setpoint in cool mode."""
    base_coordinator_data[Attribute.MODE] = 3
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_TEMPERATURE] == 25.0


async def test_climate_target_temperature_heat_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
    base_coordinator_data: dict,
) -> None:
    """Test target temperature returns heat setpoint in heat mode."""
    base_coordinator_data[Attribute.MODE] = 2
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_TEMPERATURE] == 20.0


async def test_climate_set_temperature_auto(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
    mock_client: MagicMock,
) -> None:
    """Test setting temperature in auto mode with high/low."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_temperature",
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_TARGET_TEMP_HIGH: 26.0,
            ATTR_TARGET_TEMP_LOW: 19.0,
        },
        blocking=True,
    )

    mock_client.update_setpoint.assert_called_once_with(26.0, 19.0)
    mock_client.read_control.assert_called()


async def test_climate_set_temperature_single_cool(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
    mock_client: MagicMock,
    base_coordinator_data: dict,
) -> None:
    """Test setting single temperature in cool mode."""
    base_coordinator_data[Attribute.MODE] = 3
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_temperature",
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_TEMPERATURE: 24.0,
        },
        blocking=True,
    )

    mock_client.update_setpoint.assert_called_once_with(24.0, 0)


async def test_climate_set_temperature_single_heat(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
    mock_client: MagicMock,
    base_coordinator_data: dict,
) -> None:
    """Test setting single temperature in heat mode."""
    base_coordinator_data[Attribute.MODE] = 2
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_temperature",
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_TEMPERATURE: 21.0,
        },
        blocking=True,
    )

    mock_client.update_setpoint.assert_called_once_with(0, 21.0)


async def test_climate_set_temperature_high_only(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
    mock_client: MagicMock,
) -> None:
    """Test setting only target_temp_high in auto mode."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_temperature",
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_TARGET_TEMP_HIGH: 27.0,
            ATTR_TARGET_TEMP_LOW: 18.0,
        },
        blocking=True,
    )

    mock_client.update_setpoint.assert_called_once_with(27.0, 18.0)


async def test_climate_set_humidity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
    mock_client: MagicMock,
) -> None:
    """Test setting humidity."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_humidity",
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_HUMIDITY: 40,
        },
        blocking=True,
    )

    mock_client.set_humidification_setpoint.assert_called_once_with(40)


async def test_climate_set_fan_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
    mock_client: MagicMock,
) -> None:
    """Test setting fan mode."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_fan_mode",
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_FAN_MODE: FAN_ON,
        },
        blocking=True,
    )

    mock_client.update_fan_mode.assert_called_once_with(1)
    mock_client.read_control.assert_called()


async def test_climate_set_fan_mode_circulate(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
    mock_client: MagicMock,
) -> None:
    """Test setting fan mode to circulate."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_fan_mode",
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_FAN_MODE: "Circulate",
        },
        blocking=True,
    )

    mock_client.update_fan_mode.assert_called_once_with(3)


async def test_climate_set_hvac_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
    mock_client: MagicMock,
) -> None:
    """Test setting HVAC mode."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_hvac_mode",
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_HVAC_MODE: HVACMode.HEAT,
        },
        blocking=True,
    )

    mock_client.update_mode.assert_called_once_with(2)
    mock_client.read_control.assert_called()


async def test_climate_set_preset_away(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
    mock_client: MagicMock,
) -> None:
    """Test setting preset mode to away."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_preset_mode",
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_PRESET_MODE: PRESET_AWAY,
        },
        blocking=True,
    )

    mock_client.set_hold.assert_called_once_with(3)
    mock_client.read_scheduling.assert_called()


async def test_climate_set_preset_vacation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
    mock_client: MagicMock,
) -> None:
    """Test setting preset mode to vacation."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_preset_mode",
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_PRESET_MODE: "Vacation",
        },
        blocking=True,
    )

    mock_client.set_hold.assert_called_once_with(4)


async def test_climate_set_preset_none(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
    mock_client: MagicMock,
) -> None:
    """Test clearing preset mode."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_preset_mode",
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_PRESET_MODE: PRESET_NONE,
        },
        blocking=True,
    )

    mock_client.set_hold.assert_called_once_with(0)


async def test_climate_set_hvac_mode_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
    mock_client: MagicMock,
) -> None:
    """Test setting HVAC mode to off."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_hvac_mode",
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_HVAC_MODE: HVACMode.OFF,
        },
        blocking=True,
    )

    mock_client.update_mode.assert_called_once_with(1)
    mock_client.read_control.assert_called()


async def test_climate_preset_modes_with_hold(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
    base_coordinator_data: dict,
) -> None:
    """Test preset modes list includes temporary hold when active."""
    base_coordinator_data[Attribute.HOLD] = 1
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes["preset_mode"] == "Temporary"
    assert "Temporary" in state.attributes["preset_modes"]


async def test_climate_preset_modes_permanent_hold(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
    base_coordinator_data: dict,
) -> None:
    """Test preset modes list includes permanent hold when active."""
    base_coordinator_data[Attribute.HOLD] = 2
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes["preset_mode"] == "Permanent"
    assert "Permanent" in state.attributes["preset_modes"]


async def test_climate_no_hvac_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
    base_coordinator_data: dict,
) -> None:
    """Test climate with no mode set."""
    del base_coordinator_data[Attribute.MODE]
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state.state == "unknown"


async def test_climate_no_hvac_modes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
    base_coordinator_data: dict,
) -> None:
    """Test climate with no thermostat modes set."""
    del base_coordinator_data[Attribute.THERMOSTAT_MODES]
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes["hvac_modes"] == []


async def test_climate_no_fan_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
    base_coordinator_data: dict,
) -> None:
    """Test climate with no fan mode set."""
    del base_coordinator_data[Attribute.FAN_MODE]
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes.get("fan_mode") is None
