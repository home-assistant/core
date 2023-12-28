"""Test Netgear LTE integration."""
from homeassistant.components.netgear_lte.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import CONF_DATA


async def test_setup_unload(hass: HomeAssistant, setup_integration: None) -> None:
    """Test setup and unload."""
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.state == ConfigEntryState.LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.data == CONF_DATA

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.data.get(DOMAIN)


async def test_async_setup_entry_not_ready(
    hass: HomeAssistant, setup_cannot_connect: None
) -> None:
    """Test that it throws ConfigEntryNotReady when exception occurs during setup."""
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state == ConfigEntryState.SETUP_RETRY


async def test_device(hass: HomeAssistant, setup_integration: None) -> None:
    """Test device info."""
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    device_registry = dr.async_get(hass)
    await hass.async_block_till_done()
    device = device_registry.async_get_device(identifiers={(DOMAIN, entry.unique_id)})

    assert device.configuration_url == "http://192.168.5.1"
    assert device.manufacturer == "Netgear"
    assert device.model == "LM1200"
    assert device.name == "Netgear LM1200"
    assert device.serial_number == "FFFFFFFFFFFFF"
    assert device.sw_version == "EC25AFFDR07A09M4G"
    assert device.hw_version == "1.0"
