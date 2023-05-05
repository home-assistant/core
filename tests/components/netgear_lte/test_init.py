"""Test Netgear LTE integration."""
from homeassistant.components.netgear_lte.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import CONF_DATA, ComponentSetup


async def test_setup(
    hass: HomeAssistant, setup_integration: ComponentSetup, connection
) -> None:
    """Test setup."""
    await setup_integration()
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.state == ConfigEntryState.LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.data == CONF_DATA


async def test_async_setup_entry_not_ready(
    hass: HomeAssistant, setup_integration: ComponentSetup, cannot_connect
) -> None:
    """Test that it throws ConfigEntryNotReady when exception occurs during setup."""
    await setup_integration()
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state == ConfigEntryState.SETUP_RETRY
