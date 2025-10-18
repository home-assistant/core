"""Tests for BSBLan entity classes."""

from unittest.mock import MagicMock

from homeassistant.components.bsblan.entity import BSBLanSlowEntity
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_slow_entity_initialization(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bsblan: MagicMock,
) -> None:
    """Test BSBLanSlowEntity initialization."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Get the runtime data
    data = mock_config_entry.runtime_data

    # Create a slow entity
    slow_entity = BSBLanSlowEntity(data.slow_coordinator, data)

    # Verify entity attributes
    assert slow_entity._attr_has_entity_name is True
    assert slow_entity._attr_device_info is not None
    device_info = slow_entity._attr_device_info
    assert device_info.get("identifiers") is not None
    assert device_info.get("manufacturer") == "BSBLAN Inc."
