"""Tests for the BACnet integration setup."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.components.bacnet.const import (
    CONF_ENTRY_TYPE,
    CONF_INTERFACE,
    DOMAIN,
    ENTRY_TYPE_HUB,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import (
    create_mock_device_config_entry,
    create_mock_hub_config_entry,
    init_integration_with_hub,
)

from tests.common import MockConfigEntry


async def test_async_setup_entry(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test a successful setup entry."""
    hub_entry, device_entry = await init_integration_with_hub(hass)

    assert hub_entry.state is ConfigEntryState.LOADED
    assert device_entry.state is ConfigEntryState.LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 2


async def test_config_not_ready_connect_error(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test setup failure when BACnet connection fails."""
    mock_bacnet_client.connect.side_effect = OSError("Connection refused")

    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        title="BACnet Client (eth0)",
        data={
            CONF_ENTRY_TYPE: ENTRY_TYPE_HUB,
            CONF_INTERFACE: "eth0",
        },
    )

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_config_not_ready_device_offline(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test setup failure when BACnet device is not found."""
    # Set up hub first
    hub_entry = create_mock_hub_config_entry()
    hub_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()

    # Make device discovery return empty
    mock_bacnet_client.discover_devices.return_value = []

    device_entry = create_mock_device_config_entry(hub_entry.entry_id)
    device_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(device_entry.entry_id)
    assert device_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(hass: HomeAssistant, mock_bacnet_client: AsyncMock) -> None:
    """Test successful unload of entry."""
    hub_entry, device_entry = await init_integration_with_hub(hass)

    assert device_entry.state is ConfigEntryState.LOADED

    # Unload device entry
    assert await hass.config_entries.async_unload(device_entry.entry_id)
    await hass.async_block_till_done()
    assert device_entry.state is ConfigEntryState.NOT_LOADED

    # Unload hub entry
    assert await hass.config_entries.async_unload(hub_entry.entry_id)
    await hass.async_block_till_done()
    assert hub_entry.state is ConfigEntryState.NOT_LOADED
    mock_bacnet_client.disconnect.assert_called()


async def test_device_setup_fails_when_hub_not_ready(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
) -> None:
    """Test device setup fails when hub connection fails."""
    # Make the hub's connect fail so it stays in SETUP_RETRY
    mock_bacnet_client.connect.side_effect = OSError("Connection refused")

    hub_entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        title="BACnet Client (eth0)",
        data={
            CONF_ENTRY_TYPE: ENTRY_TYPE_HUB,
            CONF_INTERFACE: "eth0",
        },
    )
    hub_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()
    assert hub_entry.state is ConfigEntryState.SETUP_RETRY

    # Create device entry that references the hub
    device_entry = create_mock_device_config_entry(hub_entry.entry_id)
    device_entry.add_to_hass(hass)

    # Try to set up device - should fail since hub is not loaded
    await hass.config_entries.async_setup(device_entry.entry_id)
    await hass.async_block_till_done()

    assert device_entry.state is ConfigEntryState.SETUP_RETRY


async def test_device_setup_fails_when_hub_missing(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test device setup fails when hub entry doesn't exist."""
    # Create device entry with fake hub ID
    device_entry = create_mock_device_config_entry("nonexistent_hub_id")
    device_entry.add_to_hass(hass)

    # Try to set up device - should fail with ConfigEntryNotReady
    await hass.config_entries.async_setup(device_entry.entry_id)
    await hass.async_block_till_done()

    assert device_entry.state is ConfigEntryState.SETUP_RETRY


async def test_hub_and_device_setup_success(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test successful setup of hub and device entries."""
    # Create and set up hub
    hub_entry = create_mock_hub_config_entry()
    hub_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()

    assert hub_entry.state is ConfigEntryState.LOADED
    assert hasattr(hub_entry, "runtime_data")
    assert hub_entry.runtime_data.client is not None

    # Create and set up device
    device_entry = create_mock_device_config_entry(hub_entry.entry_id)
    device_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(device_entry.entry_id)
    await hass.async_block_till_done()

    assert device_entry.state is ConfigEntryState.LOADED
    assert hasattr(device_entry, "runtime_data")
    assert device_entry.runtime_data.coordinator is not None


async def test_hub_removal_removes_devices(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test that removing hub also removes associated devices."""
    # Create and set up hub
    hub_entry = create_mock_hub_config_entry()
    hub_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(hub_entry.entry_id)
    await hass.async_block_till_done()

    # Create and set up device
    device_entry = create_mock_device_config_entry(hub_entry.entry_id)
    device_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(device_entry.entry_id)
    await hass.async_block_till_done()

    # Verify both entries exist
    assert len(hass.config_entries.async_entries(DOMAIN)) == 2

    # Remove hub entry
    await hass.config_entries.async_remove(hub_entry.entry_id)
    await hass.async_block_till_done()

    # Verify both hub and device entries are removed
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0
