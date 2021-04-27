"""Test the Cloudflare integration."""
from pycfdns.exceptions import CloudflareConnectionException

from homeassistant.components.cloudflare.const import DOMAIN, SERVICE_UPDATE_RECORDS
from homeassistant.config_entries import (
    ENTRY_STATE_LOADED,
    ENTRY_STATE_NOT_LOADED,
    ENTRY_STATE_SETUP_RETRY,
)

from . import ENTRY_CONFIG, init_integration

from tests.common import MockConfigEntry


async def test_unload_entry(hass, cfupdate):
    """Test successful unload of entry."""
    entry = await init_integration(hass)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state == ENTRY_STATE_LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == ENTRY_STATE_NOT_LOADED
    assert not hass.data.get(DOMAIN)


async def test_async_setup_raises_entry_not_ready(hass, cfupdate):
    """Test that it throws ConfigEntryNotReady when exception occurs during setup."""
    instance = cfupdate.return_value

    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_CONFIG)
    entry.add_to_hass(hass)

    instance.get_zone_id.side_effect = CloudflareConnectionException()
    await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state == ENTRY_STATE_SETUP_RETRY


async def test_integration_services(hass, cfupdate):
    """Test integration services."""
    instance = cfupdate.return_value

    entry = await init_integration(hass)
    assert entry.state == ENTRY_STATE_LOADED

    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_RECORDS,
        {},
        blocking=True,
    )
    await hass.async_block_till_done()

    instance.update_records.assert_called_once()
