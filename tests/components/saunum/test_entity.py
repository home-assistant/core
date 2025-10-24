"""Test entity base class for Saunum Leil Sauna Control Unit."""

from unittest.mock import patch

from homeassistant.components.saunum.entity import LeilSaunaEntity
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_entity_base_class_initialization(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_coordinator,
) -> None:
    """Test that the base entity class properly initializes."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.saunum.PLATFORMS", [Platform.CLIMATE]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Get the coordinator from runtime data
    coordinator = mock_config_entry.runtime_data

    # Create a test entity using the base class
    test_entity = LeilSaunaEntity(coordinator, "test_entity")

    # Verify entity attributes set by base class
    assert test_entity._attr_has_entity_name is True
    assert test_entity._attr_unique_id == f"{mock_config_entry.entry_id}_test_entity"
    assert test_entity._attr_device_info is not None
    assert test_entity._attr_device_info["identifiers"] == {
        ("saunum", mock_config_entry.entry_id)
    }
    assert test_entity._attr_device_info["name"] == "Saunum Leil"
    assert test_entity._attr_device_info["manufacturer"] == "Saunum"
    assert test_entity._attr_device_info["model"] == "Leil Touch Panel"


async def test_entity_coordinator_property(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_modbus_coordinator,
) -> None:
    """Test that entity has access to coordinator."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.saunum.PLATFORMS", [Platform.CLIMATE]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data

    test_entity = LeilSaunaEntity(coordinator, "test_entity")

    # Verify coordinator is accessible
    assert test_entity.coordinator == coordinator
    assert test_entity.coordinator.data is not None
