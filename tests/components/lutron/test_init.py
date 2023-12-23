"""Lutron sensor tests."""
from unittest.mock import patch

from homeassistant.components.lutron.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

LEGACY_CONFIG = {DOMAIN: {
    CONF_HOST: "127.0.0.1",
    CONF_USERNAME: "lutron",
    CONF_PASSWORD: "integration",
}}



async def test_legacy_migration(hass: HomeAssistant) -> None:
    """Test migration from yaml to config flow."""
    with patch("homeassistant.components.lutron.Lutron.load_xml_db"), patch(
            "homeassistant.components.lutron.Lutron.guid", "12345678901"
    ):
        assert await async_setup_component(hass, DOMAIN, LEGACY_CONFIG)
        await hass.async_block_till_done()
        entries = hass.config_entries.async_entries(DOMAIN)
        assert len(entries) == 1
        assert entries[0].state is ConfigEntryState.LOADED
        issue_registry = ir.async_get(hass)
        assert len(issue_registry.issues) == 1
