"""OpenSky sensor tests."""
from homeassistant.components.opensky.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PLATFORM, CONF_RADIUS, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

LEGACY_CONFIG = {Platform.SENSOR: [{CONF_PLATFORM: DOMAIN, CONF_RADIUS: 10.0}]}


async def test_legacy_migration(hass: HomeAssistant) -> None:
    """Test migration from yaml to config flow."""
    assert await async_setup_component(hass, Platform.SENSOR, LEGACY_CONFIG)
    await hass.async_block_till_done()
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED
    issue_registry = ir.async_get(hass)
    assert len(issue_registry.issues) == 1
