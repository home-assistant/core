"""Tests for the BSB-Lan climate platform."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

from bsblan import BSBLANError, HeatingCircuitStatus
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    PRESET_ECO,
    PRESET_NONE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_with_selected_platforms

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

ENTITY_ID = "climate.bsb_lan"


async def test_celsius_fahrenheit(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test Celsius and Fahrenheit temperature units."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_climate_entity_properties(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the climate entity properties."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    # Test target_temperature
    mock_target_temp = MagicMock()
    mock_target_temp.value = 23.5
    mock_bsblan.state.return_value.target_temperature = mock_target_temp

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.attributes["temperature"] == 23.5

    # Test hvac_mode - BSB-Lan returns integer: 1=auto
    mock_hvac_mode = MagicMock()
    mock_hvac_mode.value = 1  # auto mode
    mock_bsblan.state.return_value.hvac_mode = mock_hvac_mode

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == HVACMode.AUTO

    # Test preset_mode - BSB-Lan mode 2 is eco/reduced
    mock_hvac_mode.value = 2  # eco mode

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.attributes["preset_mode"] == PRESET_ECO

    # Test hvac_action mapping
    mock_hvac_action = MagicMock()
    mock_hvac_action.value = HeatingCircuitStatus.COOLING_ACTIVE
    mock_bsblan.state.return_value.hvac_action = mock_hvac_action

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.attributes["hvac_action"] == HVACAction.COOLING


async def _async_set_hvac_action(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    freezer: FrozenDateTimeFactory,
    value: MagicMock | None,
) -> HVACAction | None:
    """Helper to push a new hvac_action value through coordinator."""
    mock_bsblan.state.return_value.hvac_action = value
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    return state.attributes.get("hvac_action")


async def test_hvac_action_handles_empty_and_invalid_inputs(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Ensure hvac_action gracefully handles None and malformed values."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    assert await _async_set_hvac_action(hass, mock_bsblan, freezer, None) is None

    mock_action = MagicMock()
    mock_action.value = None
    assert await _async_set_hvac_action(hass, mock_bsblan, freezer, mock_action) is None

    mock_action.value = ""
    assert await _async_set_hvac_action(hass, mock_bsblan, freezer, mock_action) is None

    mock_action.value = "not_an_int"
    assert await _async_set_hvac_action(hass, mock_bsblan, freezer, mock_action) is None

    mock_action.value = {"unexpected": True}
    assert await _async_set_hvac_action(hass, mock_bsblan, freezer, mock_action) is None


async def test_hvac_action_uses_library_mapping(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Verify hvac_action correctly uses library's status code mapping."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    # Test a known status code is converted to action
    mock_action = MagicMock()
    mock_action.value = HeatingCircuitStatus.HEATING_COMFORT
    result = await _async_set_hvac_action(hass, mock_bsblan, freezer, mock_action)
    assert result == HVACAction.HEATING

    # Test unknown status code defaults to IDLE
    mock_action.value = 1  # Unknown status code
    result = await _async_set_hvac_action(hass, mock_bsblan, freezer, mock_action)
    assert result == HVACAction.IDLE


async def test_climate_without_current_temperature_sensor(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test climate entity when current temperature sensor is not available."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    # Set current_temperature to None to simulate no temperature sensor
    mock_bsblan.state.return_value.current_temperature = None

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Should not crash and current_temperature should be None in attributes
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes["current_temperature"] is None


async def test_climate_without_target_temperature_sensor(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test climate entity when target temperature sensor is not available."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    # Set target_temperature to None to simulate no temperature sensor
    mock_bsblan.state.return_value.target_temperature = None

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Should not crash and target temperature should be None in attributes
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes["temperature"] is None


async def test_climate_hvac_mode_none_value(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test climate entity when hvac_mode value is None."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    # Set hvac_mode.value to None
    mock_hvac_mode = MagicMock()
    mock_hvac_mode.value = None
    mock_bsblan.state.return_value.hvac_mode = mock_hvac_mode

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # State should be unknown when hvac_mode is None
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == "unknown"


async def test_climate_hvac_mode_object_none(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test climate entity when hvac_mode object itself is None."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    # Set hvac_mode to None (the object itself, not just the value)
    mock_bsblan.state.return_value.hvac_mode = None

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # State should be unknown when hvac_mode object is None
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == "unknown"
    # preset_mode should be "none" when hvac_mode object is None
    assert state.attributes["preset_mode"] == PRESET_NONE


async def test_climate_hvac_mode_string_fallback(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test climate entity with string hvac_mode value (fallback path)."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    # Set hvac_mode.value to a string (non-integer fallback)
    mock_hvac_mode = MagicMock()
    mock_hvac_mode.value = "heat"
    mock_bsblan.state.return_value.hvac_mode = mock_hvac_mode

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Should parse the string enum value
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.HEAT


# Mapping from HA HVACMode to BSB-Lan integer values for test assertions
HA_TO_BSBLAN_HVAC_MODE_TEST: dict[HVACMode, int] = {
    HVACMode.OFF: 0,
    HVACMode.AUTO: 1,
    HVACMode.HEAT: 3,
}


@pytest.mark.parametrize(
    "mode",
    [HVACMode.HEAT, HVACMode.AUTO, HVACMode.OFF],
)
async def test_async_set_hvac_mode(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mode: HVACMode,
) -> None:
    """Test setting HVAC mode via service call."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    # Call the service to set HVAC mode
    await hass.services.async_call(
        domain=CLIMATE_DOMAIN,
        service=SERVICE_SET_HVAC_MODE,
        service_data={ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: mode},
        blocking=True,
    )

    # Assert that the thermostat method was called with integer value
    expected_int = HA_TO_BSBLAN_HVAC_MODE_TEST[mode]
    mock_bsblan.thermostat.assert_called_once_with(hvac_mode=expected_int)
    mock_bsblan.thermostat.reset_mock()


@pytest.mark.parametrize(
    ("hvac_mode_int", "preset_mode"),
    [
        (1, PRESET_ECO),  # 1 = auto mode
        (1, PRESET_NONE),  # 1 = auto mode
        (3, PRESET_ECO),  # 3 = heat mode - can also set eco preset
        (0, PRESET_ECO),  # 0 = off mode - can also set eco preset
    ],
)
async def test_async_set_preset_mode_success(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    hvac_mode_int: int,
    preset_mode: str,
) -> None:
    """Test setting preset mode via service call."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    # patch hvac_mode with integer value (BSB-Lan returns integers)
    mock_hvac_mode = MagicMock()
    mock_hvac_mode.value = hvac_mode_int
    mock_bsblan.state.return_value.hvac_mode = mock_hvac_mode

    # Attempt to set the preset mode
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PRESET_MODE: preset_mode},
        blocking=True,
    )
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("target_temp"),
    [
        (8.0),  # Min temperature
        (15.0),  # Mid-range temperature
        (20.0),  # Max temperature
    ],
)
async def test_async_set_temperature(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    target_temp: float,
) -> None:
    """Test setting temperature via service call."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    await hass.services.async_call(
        domain=CLIMATE_DOMAIN,
        service=SERVICE_SET_TEMPERATURE,
        service_data={ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: target_temp},
        blocking=True,
    )
    # Assert that the thermostat method was called with the correct temperature
    mock_bsblan.thermostat.assert_called_once_with(target_temperature=target_temp)


async def test_async_set_data(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting data via service calls."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    # Test setting temperature
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 19},
        blocking=True,
    )
    mock_bsblan.thermostat.assert_called_once_with(target_temperature=19)
    mock_bsblan.thermostat.reset_mock()

    # Test setting HVAC mode - should convert to integer (3=heat)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )
    mock_bsblan.thermostat.assert_called_once_with(hvac_mode=3)  # 3 = heat
    mock_bsblan.thermostat.reset_mock()

    # Patch HVAC mode to AUTO (integer 1)
    mock_hvac_mode = MagicMock()
    mock_hvac_mode.value = 1  # 1 = auto mode
    mock_bsblan.state.return_value.hvac_mode = mock_hvac_mode

    # Test setting preset mode to ECO - should use integer 2
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PRESET_MODE: PRESET_ECO},
        blocking=True,
    )
    mock_bsblan.thermostat.assert_called_once_with(hvac_mode=2)  # 2 = eco/reduced
    mock_bsblan.thermostat.reset_mock()

    # Test setting preset mode to NONE - should use integer 1 (auto)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PRESET_MODE: PRESET_NONE},
        blocking=True,
    )
    mock_bsblan.thermostat.assert_called_once_with(hvac_mode=1)  # 1 = auto
    mock_bsblan.thermostat.reset_mock()

    # Test error handling
    mock_bsblan.thermostat.side_effect = BSBLANError("Test error")
    error_message = "An error occurred while updating the BSBLAN device"
    with pytest.raises(HomeAssistantError, match=error_message):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 20},
            blocking=True,
        )
