"""Test the STIEBEL ELTRON climate entity."""

from unittest.mock import MagicMock

from pymodbus.exceptions import ModbusException
from pystiebeleltron.lwz import OperatingMode
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_PRESET_MODE,
    PRESET_COMFORT,
    PRESET_ECO,
    HVACMode,
)
from homeassistant.components.stiebel_eltron.climate import (
    LWZ_TO_HA_HVAC,
    LWZ_TO_HA_PRESET,
    PRESET_AUTO,
    PRESET_EMERGENCY,
    PRESET_MANUAL,
    PRESET_READY,
    PRESET_WATER_HEATING,
)
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform
from tests.components.climate.common import (
    async_set_hvac_mode,
    async_set_preset_mode,
    async_set_temperature,
)

CLIMATE_UNIQUE_ID = "stiebel_eltron_001-climate_hk_1"


async def _create_climate_entry(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
) -> er.RegistryEntry:
    """Set up the integration and return the climate registry entry."""

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    for registry_entry in er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    ):
        if registry_entry.unique_id == CLIMATE_UNIQUE_ID:
            return registry_entry
    pytest.fail("Expected climate registry entry not found")


async def test_climate_entity(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test climate entity setup and state."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    # Verify entity is correctly assigned to device
    device_entry = device_registry.async_get_device(
        identifiers={("stiebel_eltron", mock_config_entry.entry_id)}
    )
    assert device_entry
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    for entity_entry in entity_entries:
        assert entity_entry.device_id == device_entry.id


@pytest.mark.parametrize(
    ("operating_mode", "expected_hvac", "expected_preset"),
    [
        (OperatingMode.AUTOMATIC, HVACMode.AUTO, PRESET_AUTO),
        (OperatingMode.MANUAL_MODE, HVACMode.HEAT, PRESET_MANUAL),
        (OperatingMode.STANDBY, HVACMode.AUTO, PRESET_READY),
        (OperatingMode.DAY_MODE, HVACMode.AUTO, PRESET_COMFORT),
        (OperatingMode.SETBACK_MODE, HVACMode.AUTO, PRESET_ECO),
        (OperatingMode.DHW, HVACMode.OFF, PRESET_WATER_HEATING),
        (OperatingMode.EMERGENCY_OPERATION, HVACMode.AUTO, PRESET_EMERGENCY),
    ],
)
async def test_climate_entity_operating_modes(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_lwz_api: MagicMock,
    operating_mode: OperatingMode,
    expected_hvac: HVACMode,
    expected_preset: str,
) -> None:
    """Test climate entity operating mode mappings."""
    # Mock the API to return the specified operating mode
    mock_lwz_api.get_operation.return_value = operating_mode

    # Create the entity and refresh its state
    climate_entry = await _create_climate_entry(
        hass, entity_registry, mock_config_entry
    )

    # Check the state and preset mode
    state = hass.states.get(climate_entry.entity_id)
    assert state is not None
    assert state.state == expected_hvac
    assert state.attributes[ATTR_PRESET_MODE] == expected_preset


async def test_climate_entity_set_hvac_mode_without_preset(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_lwz_api: MagicMock,
) -> None:
    """Test setting HVAC mode."""

    # Prepare mock
    mock_lwz_api.get_operation.return_value = None

    # Create the entity and refresh its state
    climate_entry = await _create_climate_entry(
        hass, entity_registry, mock_config_entry
    )

    # Ensure no preset is active
    state = hass.states.get(climate_entry.entity_id)
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_PRESET_MODE) is None

    # Test setting to AUTO
    mock_lwz_api.set_operation.reset_mock()
    await async_set_hvac_mode(hass, HVACMode.AUTO, climate_entry.entity_id)
    mock_lwz_api.set_operation.assert_awaited_with(OperatingMode.AUTOMATIC)

    # Test setting to HEAT
    mock_lwz_api.set_operation.reset_mock()
    await async_set_hvac_mode(hass, HVACMode.HEAT, climate_entry.entity_id)
    mock_lwz_api.set_operation.assert_awaited_with(OperatingMode.MANUAL_MODE)

    # Test setting to OFF
    mock_lwz_api.set_operation.reset_mock()
    await async_set_hvac_mode(hass, HVACMode.OFF, climate_entry.entity_id)
    mock_lwz_api.set_operation.assert_awaited_with(OperatingMode.DHW)


async def test_climate_entity_set_hvac_mode_with_preset(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_lwz_api: MagicMock,
) -> None:
    """Test that setting HVAC mode does nothing when a preset is active."""

    # Prepare mock
    mock_lwz_api.get_operation.return_value = OperatingMode.DAY_MODE
    mock_lwz_api.set_operation.reset_mock()

    # Create the entity and refresh its state
    climate_entry = await _create_climate_entry(
        hass, entity_registry, mock_config_entry
    )

    # Should not call set_operation when preset is active
    await async_set_hvac_mode(hass, HVACMode.HEAT, climate_entry.entity_id)
    mock_lwz_api.set_operation.assert_not_called()


async def test_climate_entity_set_temperature(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_lwz_api: MagicMock,
) -> None:
    """Test setting target temperature."""

    # Create the entity and refresh its state
    climate_entry = await _create_climate_entry(
        hass, entity_registry, mock_config_entry
    )
    await async_set_temperature(hass, 23.5, climate_entry.entity_id)
    mock_lwz_api.set_target_temp.assert_awaited_with(23.5)


async def test_climate_entity_set_temperature_handles_api_exception(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_lwz_api: MagicMock,
) -> None:
    """Test setting target temperature handles API exception."""

    # Create the entity and refresh its state
    climate_entry = await _create_climate_entry(
        hass, entity_registry, mock_config_entry
    )

    mock_lwz_api.set_target_temp.side_effect = ModbusException("write failed")
    with pytest.raises(HomeAssistantError):
        await async_set_temperature(hass, 24.0, climate_entry.entity_id)

    # ensure the API was attempted and no unhandled exception propagated
    mock_lwz_api.set_target_temp.assert_awaited_with(24.0)
    # optionally: assert state didn't change to new temperature


async def test_climate_entity_set_preset_mode(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_lwz_api: MagicMock,
) -> None:
    """Test setting preset mode."""

    # Create the entity and refresh its state
    climate_entry = await _create_climate_entry(
        hass, entity_registry, mock_config_entry
    )

    # Test setting to COMFORT
    mock_lwz_api.set_operation.reset_mock()
    await async_set_preset_mode(hass, PRESET_COMFORT, climate_entry.entity_id)
    mock_lwz_api.set_operation.assert_awaited_with(OperatingMode.DAY_MODE)

    # Test setting to ECO
    mock_lwz_api.set_operation.reset_mock()
    await async_set_preset_mode(hass, PRESET_ECO, climate_entry.entity_id)
    mock_lwz_api.set_operation.assert_awaited_with(OperatingMode.SETBACK_MODE)

    # Test setting to READY
    mock_lwz_api.set_operation.reset_mock()
    await async_set_preset_mode(hass, PRESET_READY, climate_entry.entity_id)
    mock_lwz_api.set_operation.assert_awaited_with(OperatingMode.STANDBY)


def test_lwz_to_ha_mappings() -> None:
    """Test LWZ to HA mappings are complete."""

    # Ensure all OperatingMode values are mapped
    for mode in OperatingMode:
        assert mode in LWZ_TO_HA_HVAC, f"Missing HVAC mapping for {mode}"
        assert mode in LWZ_TO_HA_PRESET, f"Missing preset mapping for {mode}"
