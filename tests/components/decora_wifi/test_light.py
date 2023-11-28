"""Test Decora Wifi Light Platform."""
from unittest.mock import patch

from homeassistant.components.decora_wifi import DOMAIN
from homeassistant.config_entries import ConfigEntryState, ConfigType
from homeassistant.const import CONF_PASSWORD, CONF_PLATFORM, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

LEGACY_CONFIG: ConfigType = {
    Platform.LIGHT: [
        {
            CONF_PLATFORM: DOMAIN,
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        }
    ]
}


async def test_legacy_migration(hass: HomeAssistant) -> None:
    """Test migration from yaml to config flow."""

    with patch(
        "homeassistant.components.decora_wifi.config_flow.DecoraWiFiSession.login",
        return_value=True,
    ):
        assert await async_setup_component(hass, Platform.LIGHT, LEGACY_CONFIG)
        await hass.async_block_till_done()
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED
    issue_registry = ir.async_get(hass)
    assert len(issue_registry.issues) == 1
