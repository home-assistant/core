"""Test for Sensibo integration setup."""

from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.components.sensibo.const import DOMAIN
from homeassistant.components.sensibo.util import NoUsernameError
from homeassistant.config_entries import SOURCE_USER, ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from . import ENTRY_CONFIG

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


async def test_load_unload_entry(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """Test setup and unload config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=ENTRY_CONFIG,
        entry_id="1",
        unique_id="firstnamelastname",
        version=2,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_migrate_entry(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """Test migrate entry unique id."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=ENTRY_CONFIG,
        entry_id="1",
        unique_id="someother",
        version=1,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.version == 2
    assert entry.unique_id == "firstnamelastname"


async def test_migrate_entry_fails(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """Test migrate entry fails."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=ENTRY_CONFIG,
        entry_id="1",
        unique_id="someother",
        version=1,
    )
    entry.add_to_hass(hass)

    mock_client.async_get_me.side_effect = NoUsernameError("No username returned")

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.MIGRATION_ERROR
    assert entry.version == 1
    assert entry.unique_id == "someother"


async def test_device_remove_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    load_int: ConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test we can only remove a device that no longer exists."""
    assert await async_setup_component(hass, "config", {})
    entity = entity_registry.entities["climate.hallway"]

    device_entry = device_registry.async_get(entity.device_id)
    client = await hass_ws_client(hass)
    response = await client.remove_device(device_entry.id, load_int.entry_id)
    assert not response["success"]

    dead_device_entry = device_registry.async_get_or_create(
        config_entry_id=load_int.entry_id,
        identifiers={(DOMAIN, "remove-device-id")},
    )
    response = await client.remove_device(dead_device_entry.id, load_int.entry_id)
    assert response["success"]
