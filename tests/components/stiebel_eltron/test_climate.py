"""Test the STIEBEL ELTRON climate entity."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.climate import PRESET_ECO, ClimateEntityFeature, HVACMode
from homeassistant.components.stiebel_eltron.climate import (
    PRESET_DAY,
    PRESET_EMERGENCY,
    PRESET_SETBACK,
    SUPPORT_HVAC,
    SUPPORT_PRESET,
    StiebelEltron,
    async_setup_entry,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_climate_entity_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_stiebel_eltron_client: MagicMock,
) -> None:
    """Test the climate entity is set up correctly."""

    # Mock the async_add_entities callback
    async_add_entities = MagicMock(spec=AddConfigEntryEntitiesCallback)

    # Setup mock config entry with runtime data
    mock_config_entry.runtime_data = mock_stiebel_eltron_client

    # Setup the platform
    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    # Verify entity was added
    async_add_entities.assert_called_once()
    entities = async_add_entities.call_args[0][0]
    assert len(entities) == 1
    entity = entities[0]
    assert isinstance(entity, StiebelEltron)


async def test_climate_entity_attributes(mock_stiebel_eltron_client: MagicMock) -> None:
    """Test climate entity attributes."""

    entity = StiebelEltron("Test Device", mock_stiebel_eltron_client)
    entity.update()

    # Test basic attributes
    assert entity.temperature_unit == UnitOfTemperature.CELSIUS
    assert entity.target_temperature_step == 0.1
    assert entity.min_temp == 10.0
    assert entity.max_temp == 30.0
    assert entity.hvac_modes == SUPPORT_HVAC
    assert entity.preset_modes == SUPPORT_PRESET
    assert entity.supported_features == (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )

    # Test state attributes
    assert entity.target_temperature == 22.5
    assert entity.current_temperature == 21.0
    assert entity.current_humidity == 45.0
    assert entity.hvac_mode == HVACMode.AUTO
    assert entity.preset_mode == PRESET_DAY

    # Test extra state attributes
    assert entity.extra_state_attributes == {"filter_alarm": False}


@pytest.mark.parametrize(
    ("operating_mode", "expected_hvac", "expected_preset"),
    [
        ("AUTOMATIC", HVACMode.AUTO, None),
        ("MANUAL MODE", HVACMode.HEAT, None),
        ("STANDBY", HVACMode.AUTO, PRESET_ECO),
        ("DAY MODE", HVACMode.AUTO, PRESET_DAY),
        ("SETBACK MODE", HVACMode.AUTO, PRESET_SETBACK),
        ("DHW", HVACMode.OFF, None),
        ("EMERGENCY OPERATION", HVACMode.AUTO, PRESET_EMERGENCY),
    ],
)
async def test_climate_entity_operating_modes(
    mock_stiebel_eltron_client: MagicMock,
    operating_mode: str,
    expected_hvac: HVACMode,
    expected_preset: str,
) -> None:
    """Test climate entity operating mode mappings."""
    mock_stiebel_eltron_client.get_operation.return_value = operating_mode

    entity = StiebelEltron("Test Device", mock_stiebel_eltron_client)
    entity.update()

    assert entity.hvac_mode == expected_hvac
    assert entity.preset_mode == expected_preset


async def test_climate_entity_set_hvac_mode_without_preset(
    mock_stiebel_eltron_client: MagicMock,
) -> None:
    """Test setting HVAC mode."""
    entity = StiebelEltron("Test Device", mock_stiebel_eltron_client)
    entity.update()  # Initialize attributes

    entity._operation = None  # Ensure no preset is active

    # Test setting to AUTO
    entity.set_hvac_mode(HVACMode.AUTO)
    mock_stiebel_eltron_client.set_operation.assert_called_with("AUTOMATIC")

    # Test setting to HEAT
    entity.set_hvac_mode(HVACMode.HEAT)
    mock_stiebel_eltron_client.set_operation.assert_called_with("MANUAL MODE")

    # Test setting to OFF
    entity.set_hvac_mode(HVACMode.OFF)
    mock_stiebel_eltron_client.set_operation.assert_called_with("DHW")


async def test_climate_entity_set_hvac_mode_with_preset(
    mock_stiebel_eltron_client: MagicMock,
) -> None:
    """Test that setting HVAC mode does nothing when a preset is active."""
    entity = StiebelEltron("Test Device", mock_stiebel_eltron_client)
    entity._operation = "STANDBY"  # Simulate active preset

    entity.set_hvac_mode(HVACMode.HEAT)

    # Should not call set_operation when preset is active
    mock_stiebel_eltron_client.set_operation.assert_not_called()


async def test_climate_entity_set_temperature(
    mock_stiebel_eltron_client: MagicMock,
) -> None:
    """Test setting target temperature."""
    entity = StiebelEltron("Test Device", mock_stiebel_eltron_client)
    entity.update()  # Initialize attributes

    entity.set_temperature(**{ATTR_TEMPERATURE: 23.5})
    mock_stiebel_eltron_client.set_target_temp.assert_called_with(23.5)


async def test_climate_entity_set_preset_mode(
    mock_stiebel_eltron_client: MagicMock,
) -> None:
    """Test setting preset mode."""
    entity = StiebelEltron("Test Device", mock_stiebel_eltron_client)
    entity.update()  # Initialize attributes

    # Test setting to ECO
    entity.set_preset_mode(PRESET_ECO)
    mock_stiebel_eltron_client.set_operation.assert_called_with("STANDBY")
    # Test setting to DAY
    entity.set_preset_mode(PRESET_DAY)
    mock_stiebel_eltron_client.set_operation.assert_called_with("DAY MODE")
    # Test setting to SETBACK
    entity.set_preset_mode(PRESET_SETBACK)
    mock_stiebel_eltron_client.set_operation.assert_called_with("SETBACK MODE")
    # Test setting to EMERGENCY
    entity.set_preset_mode(PRESET_EMERGENCY)
    mock_stiebel_eltron_client.set_operation.assert_called_with("EMERGENCY OPERATION")


async def test_climate_entity_no_operation_data(
    mock_stiebel_eltron_client: MagicMock,
) -> None:
    """Test climate entity when no operation data is available."""
    mock_stiebel_eltron_client.get_operation.return_value = None

    entity = StiebelEltron("Test Device", mock_stiebel_eltron_client)
    entity.update()

    assert entity.hvac_mode is None
    assert entity.preset_mode is None
