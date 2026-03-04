"""Tests for the BACnet integration setup."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.components.bacnet.bacnet_client import BACnetDeviceInfo
from homeassistant.components.bacnet.const import (
    CONF_DEVICE_ADDRESS,
    CONF_DEVICE_ID,
    CONF_DEVICES,
    CONF_INTERFACE,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import (
    MOCK_DEVICE_ID,
    MOCK_DEVICE_KEY,
    create_mock_hub_config_entry,
    create_mock_hub_only_config_entry,
    init_integration,
)
from .conftest import _create_mock_device_info

from tests.common import MockConfigEntry


async def test_async_setup_entry(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test a successful setup entry."""
    entry = await init_integration(hass)

    assert entry.state is ConfigEntryState.LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_config_not_ready_connect_error(
    hass: HomeAssistant, mock_bacnet_client: AsyncMock
) -> None:
    """Test setup failure when BACnet connection fails."""
    mock_bacnet_client.connect.side_effect = OSError("Connection refused")

    entry = MockConfigEntry(
        domain=DOMAIN,
        version=3,
        title="BACnet Client (eth0)",
        data={
            CONF_INTERFACE: "eth0",
            CONF_DEVICES: {},
        },
    )

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_offline_device_skipped(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test that offline devices are skipped and the hub still loads."""
    # Override side_effect to always return empty (simulates all devices offline)
    mock_bacnet_client.discover_devices.side_effect = None
    mock_bacnet_client.discover_devices.return_value = []

    entry = create_mock_hub_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.LOADED
    assert len(entry.runtime_data.coordinators) == 0


async def test_unload_entry(hass: HomeAssistant, mock_bacnet_client: AsyncMock) -> None:
    """Test successful unload of entry."""
    entry = await init_integration(hass)

    assert entry.state is ConfigEntryState.LOADED

    # Unload entry
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    mock_bacnet_client.disconnect.assert_called()


async def test_hub_setup_success(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test successful setup of hub entry with device in data."""
    entry = create_mock_hub_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert hasattr(entry, "runtime_data")
    assert entry.runtime_data.client is not None
    assert MOCK_DEVICE_KEY in entry.runtime_data.coordinators


async def test_hub_only_setup_success(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test successful setup of hub entry without any devices."""
    entry = create_mock_hub_only_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.client is not None
    assert len(entry.runtime_data.coordinators) == 0


async def test_no_subentries_created(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test that devices are stored in entry.data, not as subentries."""
    entry = create_mock_hub_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Devices must be in entry.data["devices"], not in subentries
    assert CONF_DEVICES in entry.data
    assert len(entry.data[CONF_DEVICES]) == 1
    assert len(entry.subentries) == 0


async def test_device_discovery_exception_skipped(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test that a device discovery exception skips the device."""
    mock_bacnet_client.discover_devices.side_effect = RuntimeError("network error")

    entry = create_mock_hub_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert len(entry.runtime_data.coordinators) == 0


async def test_background_discovery_fires_flows(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test that background discovery fires discovery flows for new devices."""
    new_device = BACnetDeviceInfo(
        device_id=9999,
        address="192.168.1.200:47808",
        name="New Device",
        vendor_name="Vendor",
        model_name="Model",
    )

    async def _discover(
        timeout: int = 5,
        low_limit: int | None = None,
        high_limit: int | None = None,
    ) -> list:
        if low_limit is not None:
            if low_limit <= MOCK_DEVICE_ID <= (high_limit or low_limit):
                return [_create_mock_device_info()]
            return []
        return [new_device]

    mock_bacnet_client.discover_devices.side_effect = _discover

    entry = create_mock_hub_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert len(entry.runtime_data.discovered_devices) == 1
    assert entry.runtime_data.discovered_devices[0].device_id == 9999


async def test_background_discovery_exception_handled(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test background discovery handles exceptions gracefully."""

    async def _discover(
        timeout: int = 5,
        low_limit: int | None = None,
        high_limit: int | None = None,
    ) -> list:
        if low_limit is not None:
            return []
        raise RuntimeError("broadcast failed")

    mock_bacnet_client.discover_devices.side_effect = _discover

    entry = create_mock_hub_only_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED


async def test_background_discovery_no_devices(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test background discovery handles empty results."""
    entry = create_mock_hub_only_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert len(entry.runtime_data.discovered_devices) == 0


async def test_remove_entry_aborts_discovery_flows(
    hass: HomeAssistant,
    mock_bacnet_client: AsyncMock,
    mock_resolve_interface_to_ip: AsyncMock,
) -> None:
    """Test removing a hub entry aborts its pending discovery flows."""
    entry = create_mock_hub_only_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Start a discovery flow tied to this hub
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "discovery"},
        data={
            CONF_DEVICE_ID: 5678,
            CONF_DEVICE_ADDRESS: "192.168.1.200:47808",
            "device_name": "Pending Device",
            "hub_entry_id": entry.entry_id,
        },
    )
    assert result["type"].value == "form"

    # There should be a discovery flow in progress
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) >= 1

    # Remove the entry
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    # Discovery flows for this hub should be aborted
    flows_after = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    hub_flows = [
        f for f in flows_after if f["context"].get("hub_entry_id") == entry.entry_id
    ]
    assert len(hub_flows) == 0
