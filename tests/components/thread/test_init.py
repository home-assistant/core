"""Test the Thread integration."""

from homeassistant.components import thread
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def test_create_entry(hass: HomeAssistant) -> None:
    """Test an entry is created by async_setup."""
    assert len(hass.config_entries.async_entries(thread.DOMAIN)) == 0
    assert await async_setup_component(hass, thread.DOMAIN, {})
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(thread.DOMAIN)) == 1


async def test_remove_entry(hass: HomeAssistant, thread_config_entry) -> None:
    """Test removing the entry."""

    config_entry = hass.config_entries.async_entries(thread.DOMAIN)[0]
    assert await hass.config_entries.async_remove(config_entry.entry_id) == {
        "require_restart": False
    }


async def test_import_once(hass: HomeAssistant, thread_config_entry) -> None:
    """Test only a single entry is created."""
    await hass.async_block_till_done()
    assert len(hass.config_entries.async_entries(thread.DOMAIN)) == 1
