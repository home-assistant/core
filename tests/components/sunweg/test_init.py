"""Tests for the Sun WEG init."""

from homeassistant.components.sunweg.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import SUNWEG_MOCK_ENTRY


async def test_methods(hass: HomeAssistant) -> None:
    """Test methods."""
    mock_entry = SUNWEG_MOCK_ENTRY
    mock_entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, mock_entry)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(mock_entry.entry_id)
