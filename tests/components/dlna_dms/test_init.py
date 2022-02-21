"""Test the DLNA DMS component setup, cleanup, and module-level functions."""

from unittest.mock import Mock

from homeassistant.components.dlna_dms.const import DOMAIN
from homeassistant.components.dlna_dms.dms import DlnaDmsData
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_resource_lifecycle(
    hass: HomeAssistant,
    domain_data_mock: DlnaDmsData,
    config_entry_mock: MockConfigEntry,
    ssdp_scanner_mock: Mock,
    dms_device_mock: Mock,
) -> None:
    """Test that resources are acquired/released as the entity is setup/unloaded."""
    # Set up the config entry
    config_entry_mock.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {}) is True
    await hass.async_block_till_done()

    # Check the entity is created and working
    assert len(domain_data_mock.devices) == 1
    assert len(domain_data_mock.sources) == 1
    entity = next(iter(domain_data_mock.devices.values()))
    assert entity.available is True

    # Check update listeners are subscribed
    assert len(config_entry_mock.update_listeners) == 1
    assert ssdp_scanner_mock.async_register_callback.await_count == 2
    assert ssdp_scanner_mock.async_register_callback.return_value.call_count == 0

    # Check event notifiers are not subscribed - dlna_dms doesn't use them
    assert dms_device_mock.async_subscribe_services.await_count == 0
    assert dms_device_mock.async_unsubscribe_services.await_count == 0
    assert dms_device_mock.on_event is None

    # Unload the config entry
    assert await hass.config_entries.async_remove(config_entry_mock.entry_id) == {
        "require_restart": False
    }

    # Check update listeners are released
    assert not config_entry_mock.update_listeners
    assert ssdp_scanner_mock.async_register_callback.await_count == 2
    assert ssdp_scanner_mock.async_register_callback.return_value.call_count == 2

    # Check event notifiers are still not subscribed
    assert dms_device_mock.async_subscribe_services.await_count == 0
    assert dms_device_mock.async_unsubscribe_services.await_count == 0
    assert dms_device_mock.on_event is None

    # Check entity is gone
    assert not domain_data_mock.devices
    assert not domain_data_mock.sources
