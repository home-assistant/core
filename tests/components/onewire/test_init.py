"""Tests for 1-Wire config flow."""

from unittest.mock import MagicMock, patch

from aio_ownet.exceptions import OWServerReturnError
from freezegun.api import FrozenDateTimeFactory
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
    owproxy.return_value.read.side_effect = OWServerReturnError(-1)
    owproxy.return_value.dir.side_effect = OWServerReturnError(-1)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry, owproxy: MagicMock
) -> None:
    """Test being able to unload an entry."""
    setup_owproxy_mock_devices(owproxy, [])
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED


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


async def test_device_via_device_links(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    owproxy: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a coupler branch device links to its parent via via_device_id."""
    # The 1F coupler exposes a 1D device on its "main" branch.
    setup_owproxy_mock_devices(owproxy, ["1F.111111111111"])
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    parent_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "1F.111111111111"), config_entry.entry_id
    )
    assert parent_device is not None

    child_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "1D.111111111111"), config_entry.entry_id
    )
    assert child_device is not None
    assert child_device.via_device_id == parent_device.id


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
    device = device_registry.async_get_device_by_identifier((DOMAIN, live_id), entry_id)
    client = await hass_ws_client(hass)
    response = await client.remove_device(device.id)
    assert not response["success"]
    assert len(dr.async_entries_for_config_entry(device_registry, entry_id)) == 2
    assert (
        device_registry.async_get_device_by_identifier((DOMAIN, live_id), entry_id)
        is not None
    )

    # Try to remove "28.111111111111" - succeeds as it is dead
    device = device_registry.async_get_device_by_identifier((DOMAIN, dead_id), entry_id)
    response = await client.remove_device(device.id)
    assert response["success"]
    assert len(dr.async_entries_for_config_entry(device_registry, entry_id)) == 1
    assert (
        device_registry.async_get_device_by_identifier((DOMAIN, dead_id), entry_id)
        is None
    )
