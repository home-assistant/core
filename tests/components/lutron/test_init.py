"""Test Lutron integration setup."""

from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant, mock_lutron: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test setting up the integration."""
    mock_config_entry.add_to_hass(hass)

    assert await async_setup_component(hass, "lutron", {})
    await hass.async_block_till_done()

    assert mock_config_entry.runtime_data.client is mock_lutron
    assert len(mock_config_entry.runtime_data.lights) == 1


async def test_unload_entry(
    hass: HomeAssistant, mock_lutron: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test unloading the integration."""
    mock_config_entry.add_to_hass(hass)

    assert await async_setup_component(hass, "lutron", {})
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
