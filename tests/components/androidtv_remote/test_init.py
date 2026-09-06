"""Tests for the Android TV Remote integration."""

from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock

from androidtvremote2 import CannotConnect, InvalidAuth

from homeassistant.components.androidtv_remote.const import DOMAIN
from homeassistant.components.androidtv_remote.helpers import async_get_nic_mac_address
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


async def test_load_unload_config_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: MagicMock
) -> None:
    """Test the Android TV Remote configuration entry loading/unloading."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_api.async_connect.call_count == 1
    assert mock_api.keep_reconnecting.call_count == 1

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert mock_api.disconnect.call_count == 1


async def test_config_entry_not_ready(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: MagicMock
) -> None:
    """Test the Android TV Remote configuration entry not ready."""
    mock_api.async_connect = AsyncMock(side_effect=CannotConnect())

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_api.async_connect.call_count == 1
    assert mock_api.keep_reconnecting.call_count == 0


async def test_config_entry_reauth_at_setup(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: MagicMock
) -> None:
    """Test the Android TV Remote configuration entry needs reauth at setup."""
    mock_api.async_connect = AsyncMock(side_effect=InvalidAuth())

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert any(mock_config_entry.async_get_active_flows(hass, {"reauth"}))
    assert mock_api.async_connect.call_count == 1
    assert mock_api.keep_reconnecting.call_count == 0


async def test_config_entry_reauth_while_reconnecting(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: MagicMock
) -> None:
    """Test the Android TV Remote config entry needs reauth.

    Occurs while reconnecting.
    """
    invalid_auth_callback: Callable | None = None

    def mocked_keep_reconnecting(callback: Callable):
        nonlocal invalid_auth_callback
        invalid_auth_callback = callback

    mock_api.keep_reconnecting.side_effect = mocked_keep_reconnecting

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert not any(mock_config_entry.async_get_active_flows(hass, {"reauth"}))
    assert mock_api.async_connect.call_count == 1
    assert mock_api.keep_reconnecting.call_count == 1

    assert invalid_auth_callback is not None
    invalid_auth_callback()
    await hass.async_block_till_done()
    assert any(mock_config_entry.async_get_active_flows(hass, {"reauth"}))


async def test_disconnect_on_stop(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: MagicMock
) -> None:
    """Test we close the connection with the Android TV when Home Assistants stops."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_api.async_connect.call_count == 1
    assert mock_api.keep_reconnecting.call_count == 1

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    assert mock_api.disconnect.call_count == 1


async def test_device_registry_connections(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that the device registry entry contains both Bluetooth and NIC MAC addresses."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_config_entry.unique_id), mock_config_entry.entry_id
    )
    assert device is not None
    assert (dr.CONNECTION_NETWORK_MAC, "1a:2b:3c:4d:5e:6f") in device.connections
    assert (dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:11:22:33") in device.connections


async def test_device_registry_nic_mac_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
    device_registry: dr.DeviceRegistry,
    mock_get_mac_address: MagicMock,
) -> None:
    """Test setup when physical NIC MAC cannot be resolved via ARP."""
    mock_get_mac_address.return_value = None

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_config_entry.unique_id), mock_config_entry.entry_id
    )
    assert device is not None
    assert (dr.CONNECTION_NETWORK_MAC, "1a:2b:3c:4d:5e:6f") in device.connections
    assert (dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:11:22:33") not in device.connections


async def test_existing_device_registry_connections_updated(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that an existing device registry entry without NIC MAC is updated."""
    mock_config_entry.add_to_hass(hass)
    # Pre-create device with only Bluetooth MAC as existed prior to this change
    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, mock_config_entry.unique_id)},
        connections={(dr.CONNECTION_NETWORK_MAC, "1a:2b:3c:4d:5e:6f")},
    )
    assert device.connections == {(dr.CONNECTION_NETWORK_MAC, "1a:2b:3c:4d:5e:6f")}

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_config_entry.unique_id), mock_config_entry.entry_id
    )
    assert device is not None
    assert (dr.CONNECTION_NETWORK_MAC, "1a:2b:3c:4d:5e:6f") in device.connections
    assert (dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:11:22:33") in device.connections


async def test_existing_device_registry_connections_not_updated_when_nic_mac_none(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
    device_registry: dr.DeviceRegistry,
    mock_get_mac_address: MagicMock,
) -> None:
    """Test that existing device connections are preserved when nic_mac lookup fails."""
    mock_get_mac_address.return_value = None
    mock_config_entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, mock_config_entry.unique_id)},
        connections={(dr.CONNECTION_NETWORK_MAC, "1a:2b:3c:4d:5e:6f")},
    )
    assert device.connections == {(dr.CONNECTION_NETWORK_MAC, "1a:2b:3c:4d:5e:6f")}

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_config_entry.unique_id), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.connections == {(dr.CONNECTION_NETWORK_MAC, "1a:2b:3c:4d:5e:6f")}


async def test_async_get_nic_mac_address_ipv4(
    hass: HomeAssistant,
    mock_get_mac_address: MagicMock,
) -> None:
    """Test async_get_nic_mac_address with IPv4 address."""
    mac = await async_get_nic_mac_address(hass, "192.168.1.100")
    assert mac == "aa:bb:cc:11:22:33"
    assert mock_get_mac_address.call_args.kwargs == {"ip": "192.168.1.100"}


async def test_async_get_nic_mac_address_ipv6(
    hass: HomeAssistant,
    mock_get_mac_address: MagicMock,
) -> None:
    """Test async_get_nic_mac_address with scoped IPv6 address."""
    mac = await async_get_nic_mac_address(hass, "2001:db8::1%eth0")
    assert mac == "aa:bb:cc:11:22:33"
    assert mock_get_mac_address.call_args.kwargs == {"ip6": "2001:db8::1"}


async def test_async_get_nic_mac_address_hostname(
    hass: HomeAssistant,
    mock_get_mac_address: MagicMock,
) -> None:
    """Test async_get_nic_mac_address with hostname."""
    mac = await async_get_nic_mac_address(hass, "android-tv.local")
    assert mac == "aa:bb:cc:11:22:33"
    assert mock_get_mac_address.call_args.kwargs == {"hostname": "android-tv.local"}


async def test_async_get_nic_mac_address_not_found(
    hass: HomeAssistant,
    mock_get_mac_address: MagicMock,
) -> None:
    """Test async_get_nic_mac_address when getmac returns None."""
    mock_get_mac_address.return_value = None
    mac = await async_get_nic_mac_address(hass, "192.168.1.100")
    assert mac is None
