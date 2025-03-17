"""Tests for 1-Wire config flow."""

from copy import deepcopy
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyownet import protocol
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.onewire.const import DOMAIN
from homeassistant.components.onewire.onewirehub import _DEVICE_SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from . import setup_owproxy_mock_devices
from .const import MOCK_OWPROXY_DEVICES

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.typing import WebSocketGenerator


@pytest.mark.usefixtures("owproxy_with_connerror")
async def test_connect_failure(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test connection failure raises ConfigEntryNotReady."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_listing_failure(
    hass: HomeAssistant, config_entry: MockConfigEntry, owproxy: MagicMock
) -> None:
    """Test listing failure raises ConfigEntryNotReady."""
    owproxy.return_value.dir.side_effect = protocol.OwnetError()

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("owproxy")
async def test_unload_entry(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Test being able to unload an entry."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_update_options(
    hass: HomeAssistant, config_entry: MockConfigEntry, owproxy: MagicMock
) -> None:
    """Test update options triggers reload."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state is ConfigEntryState.LOADED
    assert owproxy.call_count == 1

    new_options = deepcopy(dict(config_entry.options))
    new_options["device_options"].clear()
    hass.config_entries.async_update_entry(config_entry, options=new_options)
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state is ConfigEntryState.LOADED
    assert owproxy.call_count == 2


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_registry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    owproxy: MagicMock,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test device are correctly registered."""
    setup_owproxy_mock_devices(owproxy, MOCK_OWPROXY_DEVICES.keys())
    await hass.config_entries.async_setup(config_entry.entry_id)

    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )
    assert device_entries
    for device_entry in device_entries:
        assert device_entry == snapshot(name=f"{device_entry.name}-entry")


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_registry_delayed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    owproxy: MagicMock,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test device are correctly registered."""
    setup_owproxy_mock_devices(owproxy, [])
    await hass.config_entries.async_setup(config_entry.entry_id)

    assert not dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)

    setup_owproxy_mock_devices(owproxy, ["1F.111111111111"])
    freezer.tick(_DEVICE_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (
        len(dr.async_entries_for_config_entry(device_registry, config_entry.entry_id))
        == 2
    )


@patch("homeassistant.components.onewire._PLATFORMS", [Platform.SENSOR])
async def test_registry_cleanup(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    owproxy: MagicMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test being able to remove a disconnected device."""
    assert await async_setup_component(hass, "config", {})

    entry_id = config_entry.entry_id
    live_id = "10.111111111111"
    dead_id = "28.111111111111"

    # Initialise with two components
    setup_owproxy_mock_devices(owproxy, [live_id, dead_id])
    await hass.config_entries.async_setup(entry_id)
    await hass.async_block_till_done()

    # Reload with a device no longer on bus
    setup_owproxy_mock_devices(owproxy, [live_id])
    await hass.config_entries.async_reload(entry_id)
    await hass.async_block_till_done()
    assert len(dr.async_entries_for_config_entry(device_registry, entry_id)) == 2

    # Try to remove "10.111111111111" - fails as it is live
    device = device_registry.async_get_device(identifiers={(DOMAIN, live_id)})
    client = await hass_ws_client(hass)
    response = await client.remove_device(device.id, entry_id)
    assert not response["success"]
    assert len(dr.async_entries_for_config_entry(device_registry, entry_id)) == 2
    assert device_registry.async_get_device(identifiers={(DOMAIN, live_id)}) is not None

    # Try to remove "28.111111111111" - succeeds as it is dead
    device = device_registry.async_get_device(identifiers={(DOMAIN, dead_id)})
    response = await client.remove_device(device.id, entry_id)
    assert response["success"]
    assert len(dr.async_entries_for_config_entry(device_registry, entry_id)) == 1
    assert device_registry.async_get_device(identifiers={(DOMAIN, dead_id)}) is None
