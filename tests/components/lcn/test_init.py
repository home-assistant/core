"""Test init of LCN integration."""

from unittest.mock import Mock, patch

from pypck.connection import PchkAuthenticationError, PchkLicenseError
import pytest

from homeassistant import config_entries
from homeassistant.components.lcn.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import (
    MockConfigEntry,
    MockPchkConnectionManager,
    create_config_entry,
    init_integration,
)


async def test_async_setup_entry(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Test a successful setup entry and unload of entry."""
    await init_integration(hass, entry)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


async def test_async_setup_multiple_entries(
    hass: HomeAssistant, entry: MockConfigEntry, entry2
) -> None:
    """Test a successful setup and unload of multiple entries."""
    hass.http = Mock()
    with patch(
        "homeassistant.components.lcn.PchkConnectionManager", MockPchkConnectionManager
    ):
        for config_entry in (entry, entry2):
            await init_integration(hass, config_entry)
            assert config_entry.state is ConfigEntryState.LOADED

    assert len(hass.config_entries.async_entries(DOMAIN)) == 2

    for config_entry in (entry, entry2):
        assert await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()

        assert config_entry.state is ConfigEntryState.NOT_LOADED

    assert not hass.data.get(DOMAIN)


async def test_async_setup_entry_update(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    entry: MockConfigEntry,
) -> None:
    """Test a successful setup entry if entry with same id already exists."""
    # setup first entry
    entry.source = config_entries.SOURCE_IMPORT
    entry.add_to_hass(hass)

    # create dummy entity for LCN platform as an orphan
    dummy_entity = entity_registry.async_get_or_create(
        "switch", DOMAIN, "dummy", config_entry=entry
    )

    # create dummy device for LCN platform as an orphan
    dummy_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id, 0, 7, False)},
        via_device=(DOMAIN, entry.entry_id),
    )

    assert dummy_entity in entity_registry.entities.values()
    assert dummy_device in device_registry.devices.values()


@pytest.mark.parametrize(
    "exception", [PchkAuthenticationError, PchkLicenseError, TimeoutError]
)
async def test_async_setup_entry_raises_authentication_error(
    hass: HomeAssistant, entry: MockConfigEntry, exception: Exception
) -> None:
    """Test that an authentication error is handled properly."""
    with patch(
        "homeassistant.components.lcn.PchkConnectionManager.async_connect",
        side_effect=exception,
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


@patch("homeassistant.components.lcn.PchkConnectionManager", MockPchkConnectionManager)
async def test_migrate_1_1(hass: HomeAssistant, entry) -> None:
    """Test migration config entry."""
    entry_v1_1 = create_config_entry("pchk_v1_1", version=(1, 1))
    entry_v1_1.add_to_hass(hass)

    await hass.config_entries.async_setup(entry_v1_1.entry_id)
    await hass.async_block_till_done()

    entry_migrated = hass.config_entries.async_get_entry(entry_v1_1.entry_id)
    assert entry_migrated.state is ConfigEntryState.LOADED
    assert entry_migrated.version == 2
    assert entry_migrated.minor_version == 1
    assert entry_migrated.data == entry.data


@patch("homeassistant.components.lcn.PchkConnectionManager", MockPchkConnectionManager)
async def test_migrate_1_2(hass: HomeAssistant, entry) -> None:
    """Test migration config entry."""
    entry_v1_2 = create_config_entry("pchk_v1_2", version=(1, 2))
    entry_v1_2.add_to_hass(hass)

    await hass.config_entries.async_setup(entry_v1_2.entry_id)
    await hass.async_block_till_done()

    entry_migrated = hass.config_entries.async_get_entry(entry_v1_2.entry_id)
    assert entry_migrated.state is ConfigEntryState.LOADED
    assert entry_migrated.version == 2
    assert entry_migrated.minor_version == 1
    assert entry_migrated.data == entry.data
