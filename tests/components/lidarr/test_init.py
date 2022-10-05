"""Test Lidarr integration."""
from homeassistant.components.lidarr.const import DEFAULT_NAME, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import ComponentSetup


async def test_setup(
    hass: HomeAssistant, setup_integration: ComponentSetup, connection
) -> None:
    """Test setup."""
    await setup_integration()
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.state == ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


async def test_async_setup_entry_not_ready(
    hass: HomeAssistant, setup_integration: ComponentSetup, cannot_connect
) -> None:
    """Test that it throws ConfigEntryNotReady when exception occurs during setup."""
    await setup_integration()
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state == ConfigEntryState.SETUP_RETRY
    assert not hass.data.get(DOMAIN)


async def test_async_setup_entry_auth_failed(
    hass: HomeAssistant, setup_integration: ComponentSetup, invalid_auth
) -> None:
    """Test that it throws ConfigEntryAuthFailed when authentication fails."""
    await setup_integration()
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state == ConfigEntryState.SETUP_ERROR
    assert not hass.data.get(DOMAIN)


async def test_device_info(
    hass: HomeAssistant, setup_integration: ComponentSetup, connection
) -> None:
    """Test device info."""
    await setup_integration()
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    device_registry = dr.async_get(hass)
    await hass.async_block_till_done()
    device = device_registry.async_get_device({(DOMAIN, entry.entry_id)})

    assert device.configuration_url == "http://127.0.0.1:8668"
    assert device.identifiers == {(DOMAIN, entry.entry_id)}
    assert device.manufacturer == DEFAULT_NAME
    assert device.name == "Mock Title"
    assert device.sw_version == "10.0.0.34882"
