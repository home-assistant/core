"""Test init of LCN integration."""
from unittest.mock import patch

from pypck.connection import (
    PchkAuthenticationError,
    PchkConnectionManager,
    PchkLicenseError,
)

from homeassistant import config_entries
from homeassistant.components.lcn.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import MockPchkConnectionManager, init_integration, setup_component


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
async def test_async_setup_entry(hass, entry):
    """Test a successful setup entry and unload of entry."""
    await init_integration(hass, entry)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state == ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
async def test_async_setup_multiple_entries(hass, entry, entry2):
    """Test a successful setup and unload of multiple entries."""
    for config_entry in (entry, entry2):
        await init_integration(hass, config_entry)
        assert config_entry.state == ConfigEntryState.LOADED
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 2

    for config_entry in (entry, entry2):
        assert await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()

        assert config_entry.state == ConfigEntryState.NOT_LOADED

    assert not hass.data.get(DOMAIN)


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
async def test_async_setup_entry_update(hass, entry):
    """Test a successful setup entry if entry with same id already exists."""
    # setup first entry
    entry.source = config_entries.SOURCE_IMPORT

    # create dummy entity for LCN platform as an orphan
    entity_registry = await er.async_get_registry(hass)
    dummy_entity = entity_registry.async_get_or_create(
        "switch", DOMAIN, "dummy", config_entry=entry
    )
    assert dummy_entity in entity_registry.entities.values()

    # add entity to hass and setup (should cleanup dummy entity)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert dummy_entity not in entity_registry.entities.values()


async def test_async_setup_entry_raises_authentication_error(hass, entry):
    """Test that an authentication error is handled properly."""
    with patch.object(
        PchkConnectionManager, "async_connect", side_effect=PchkAuthenticationError
    ):
        await init_integration(hass, entry)
    assert entry.state == ConfigEntryState.SETUP_ERROR


async def test_async_setup_entry_raises_license_error(hass, entry):
    """Test that an authentication error is handled properly."""
    with patch.object(
        PchkConnectionManager, "async_connect", side_effect=PchkLicenseError
    ):
        await init_integration(hass, entry)
    assert entry.state == ConfigEntryState.SETUP_ERROR


async def test_async_setup_entry_raises_timeout_error(hass, entry):
    """Test that an authentication error is handled properly."""
    with patch.object(PchkConnectionManager, "async_connect", side_effect=TimeoutError):
        await init_integration(hass, entry)
    assert entry.state == ConfigEntryState.SETUP_ERROR


@patch("pypck.connection.PchkConnectionManager", MockPchkConnectionManager)
async def test_async_setup_from_configuration_yaml(hass):
    """Test a successful setup using data from configuration.yaml."""
    await async_setup_component(hass, "persistent_notification", {})

    with patch("homeassistant.components.lcn.async_setup_entry") as async_setup_entry:
        await setup_component(hass)

        assert async_setup_entry.await_count == 2
