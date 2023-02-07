"""Test D-Link Smart Plug setup."""
from unittest.mock import MagicMock

from homeassistant.components.dlink.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import CONF_DATA, ComponentSetup, patch_setup

from tests.common import MockConfigEntry


async def test_setup_config_and_unload(
    hass: HomeAssistant, setup_integration: ComponentSetup
) -> None:
    """Test setup and unload."""
    await setup_integration()

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.state == ConfigEntryState.LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.data == CONF_DATA

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


async def test_legacy_setup_config_and_unload(
    hass: HomeAssistant, setup_integration_legacy: ComponentSetup
) -> None:
    """Test legacy setup and unload."""
    await setup_integration_legacy()

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.state == ConfigEntryState.LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.data == CONF_DATA

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


async def test_async_setup_entry_not_ready(
    hass: HomeAssistant,
    config_entry_with_uid: MockConfigEntry,
    mocked_plug_legacy_no_auth: MagicMock,
) -> None:
    """Test that it throws ConfigEntryNotReady when exception occurs during legacy setup."""
    with patch_setup(mocked_plug_legacy_no_auth):
        await hass.config_entries.async_setup(config_entry_with_uid.entry_id)
    assert config_entry_with_uid.state == ConfigEntryState.SETUP_RETRY


async def test_device_info(
    hass: HomeAssistant, setup_integration: ComponentSetup
) -> None:
    """Test device info."""
    await setup_integration()

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device({(DOMAIN, entry.entry_id)})

    assert device.connections == {("mac", "aa:bb:cc:dd:ee:ff")}
    assert device.identifiers == {(DOMAIN, entry.entry_id)}
    assert device.manufacturer == "D-Link"
    assert device.model == "DSP-W215"
    assert device.name == "Mock Title"
