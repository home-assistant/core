"""Test Color extractor component setup process."""
from homeassistant.components.color_extractor import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component


async def test_legacy_migration(hass: HomeAssistant) -> None:
    """Test migration from yaml to config flow."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED
    issue_registry = ir.async_get(hass)
    assert len(issue_registry.issues) == 1
