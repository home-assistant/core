"""Test the DLNA DMS component setup, cleanup, and module-level functions."""

from typing import cast
from unittest.mock import Mock

from homeassistant.components.dlna_dms.const import (
    CONF_SOURCE_ID,
    CONFIG_VERSION,
    DOMAIN,
)
from homeassistant.components.dlna_dms.dms import DlnaDmsData
from homeassistant.const import CONF_DEVICE_ID, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import (
    MOCK_DEVICE_LOCATION,
    MOCK_DEVICE_NAME,
    MOCK_DEVICE_TYPE,
    MOCK_DEVICE_USN,
    MOCK_SOURCE_ID,
)

from tests.common import MockConfigEntry


async def test_resource_lifecycle(
    hass: HomeAssistant,
    aiohttp_session_requester_mock: Mock,
    config_entry_mock: MockConfigEntry,
    ssdp_scanner_mock: Mock,
    dms_device_mock: Mock,
) -> None:
    """Test that resources are acquired/released as the entity is setup/unloaded."""
    # Set up the config entry
    config_entry_mock.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {}) is True
    await hass.async_block_till_done()

    # Check the device source is created and working
    domain_data = cast(DlnaDmsData, hass.data[DOMAIN])
    assert len(domain_data.devices) == 1
    assert len(domain_data.sources) == 1
    entity = next(iter(domain_data.devices.values()))
    assert entity.available is True

    # Check listener subscriptions
    assert len(config_entry_mock.update_listeners) == 0
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

    # Check device source is gone
    assert not domain_data.devices
    assert not domain_data.sources


async def test_migrate_entry(hass: HomeAssistant) -> None:
    """Test migrating a config entry from version 1 to version 2."""
    # Create mock entry with version 1
    mock_entry = MockConfigEntry(
        unique_id=MOCK_DEVICE_USN,
        domain=DOMAIN,
        version=1,
        data={
            CONF_URL: MOCK_DEVICE_LOCATION,
            CONF_DEVICE_ID: MOCK_DEVICE_USN,
        },
        title=MOCK_DEVICE_NAME,
    )

    # Set it up
    mock_entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {}) is True
    await hass.async_block_till_done()

    # Check that it has a source_id now
    updated_entry = hass.config_entries.async_get_entry(mock_entry.entry_id)
    assert updated_entry
    assert updated_entry.version == CONFIG_VERSION
    assert updated_entry.data.get(CONF_SOURCE_ID) == MOCK_SOURCE_ID


async def test_migrate_entry_collision(
    hass: HomeAssistant, config_entry_mock: MockConfigEntry
) -> None:
    """Test migrating a config entry with a potentially colliding source ID."""
    # Use existing mock entry
    config_entry_mock.add_to_hass(hass)

    # Create mock entry with same name, and old version, that needs migrating
    mock_entry = MockConfigEntry(
        unique_id=f"udn-migrating::{MOCK_DEVICE_TYPE}",
        domain=DOMAIN,
        version=1,
        data={
            CONF_URL: "http://192.88.99.22/dms_description.xml",
            CONF_DEVICE_ID: f"different-udn::{MOCK_DEVICE_TYPE}",
        },
        title=MOCK_DEVICE_NAME,
    )
    mock_entry.add_to_hass(hass)

    # Set the integration up
    assert await async_setup_component(hass, DOMAIN, {}) is True
    await hass.async_block_till_done()

    # Check that it has a source_id now
    updated_entry = hass.config_entries.async_get_entry(mock_entry.entry_id)
    assert updated_entry
    assert updated_entry.version == CONFIG_VERSION
    assert updated_entry.data.get(CONF_SOURCE_ID) == f"{MOCK_SOURCE_ID}_1"
