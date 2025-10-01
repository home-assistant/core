"""Tests for the OpenRGB integration init."""

from unittest.mock import MagicMock, patch

from openrgb.utils import OpenRGBDisconnected
import pytest

from homeassistant.components.openrgb import async_remove_config_entry_device
from homeassistant.components.openrgb.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_client: MagicMock,
    mock_get_mac_address: MagicMock,
) -> None:
    """Test setup entry."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is not None


async def test_setup_entry_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_mac_address: MagicMock,
) -> None:
    """Test setup entry with connection error."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.openrgb.coordinator.OpenRGBClient",
        side_effect=ConnectionRefusedError,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_client: MagicMock,
    mock_get_mac_address: MagicMock,
) -> None:
    """Test unload entry."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert mock_openrgb_client.disconnect.called


async def test_async_migrate_unique_ids(
    hass: HomeAssistant,
    mock_openrgb_client: MagicMock,
    mock_get_mac_address: MagicMock,
) -> None:
    """Test migrating unique IDs when MAC address changes."""
    old_mac = "aa:bb:cc:dd:ee:ff"
    new_mac = "11:22:33:44:55:66"

    # Create config entry with migration marker
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"OpenRGB ({old_mac})",
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 6742,
            CONF_MAC: new_mac,
            "_migrate_mac": {"old": old_mac, "new": new_mac},
        },
        unique_id=new_mac,
    )
    config_entry.add_to_hass(hass)

    # Create old device and entities with old MAC
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    old_server_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, old_mac)},
        connections={(dr.CONNECTION_NETWORK_MAC, old_mac)},
        name=f"OpenRGB ({old_mac})",
    )

    old_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={
            (
                DOMAIN,
                f"{old_mac}||LEDSTRIP||Test Vendor||Test LED Strip||TEST123||Test Location",
            )
        },
        name="Test RGB Device",
        via_device=(DOMAIN, old_mac),
    )

    entity_registry.async_get_or_create(
        domain="light",
        platform=DOMAIN,
        unique_id=f"{old_mac}||LEDSTRIP||Test Vendor||Test LED Strip||TEST123||Test Location",
        config_entry=config_entry,
        device_id=old_device.id,
    )

    # Setup the integration (which should trigger migration)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify migration marker was removed
    assert "_migrate_mac" not in config_entry.data

    # Verify server device was updated
    updated_server_device = device_registry.async_get_device(
        identifiers={(DOMAIN, new_mac)}
    )
    assert updated_server_device is not None
    assert updated_server_device.id == old_server_device.id
    assert (dr.CONNECTION_NETWORK_MAC, new_mac) in updated_server_device.connections

    # Verify device identifiers were updated
    updated_device = device_registry.async_get_device(
        identifiers={
            (
                DOMAIN,
                f"{new_mac}||LEDSTRIP||Test Vendor||Test LED Strip||TEST123||Test Location",
            )
        }
    )
    assert updated_device is not None
    assert updated_device.id == old_device.id

    # Verify entity unique ID was updated
    entity = entity_registry.async_get(f"light.{DOMAIN}_test_rgb_device")
    if entity:
        assert (
            entity.unique_id
            == f"{new_mac}||LEDSTRIP||Test Vendor||Test LED Strip||TEST123||Test Location"
        )


async def test_server_device_registry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_client: MagicMock,
    mock_get_mac_address: MagicMock,
) -> None:
    """Test server device is created in device registry."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    server_device = device_registry.async_get_device(
        identifiers={(DOMAIN, "aa:bb:cc:dd:ee:ff")}
    )

    assert server_device is not None
    assert server_device.name == "OpenRGB (aa:bb:cc:dd:ee:ff)"
    assert server_device.manufacturer == "OpenRGB"
    assert server_device.model == "OpenRGB Server"
    assert server_device.sw_version == "3 (Protocol)"
    assert server_device.entry_type is dr.DeviceEntryType.SERVICE


async def test_remove_config_entry_device_server(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_client: MagicMock,
    mock_get_mac_address: MagicMock,
) -> None:
    """Test that server device cannot be removed."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    server_device = device_registry.async_get_device(
        identifiers={(DOMAIN, "aa:bb:cc:dd:ee:ff")}
    )

    assert server_device is not None

    # Try to remove server device - should be blocked
    result = await async_remove_config_entry_device(
        hass, mock_config_entry, server_device
    )

    assert result is False


async def test_remove_config_entry_device_still_connected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_client: MagicMock,
    mock_get_mac_address: MagicMock,
) -> None:
    """Test that connected devices cannot be removed."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device_registry = dr.async_get(hass)

    # Get a device that's in coordinator.data (still connected)
    devices = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    rgb_device = next(
        (d for d in devices if d.identifiers != {(DOMAIN, "aa:bb:cc:dd:ee:ff")}), None
    )

    if rgb_device:
        # Try to remove device that's still connected - should be blocked
        result = await async_remove_config_entry_device(
            hass, mock_config_entry, rgb_device
        )
        assert result is False


async def test_remove_config_entry_device_disconnected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_client: MagicMock,
    mock_get_mac_address: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that disconnected devices can be removed."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Create a device that's not in coordinator.data (disconnected)
    disconnected_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={
            (
                DOMAIN,
                "aa:bb:cc:dd:ee:ff||KEYBOARD||Old Vendor||Old Device||OLD123||Old Location",
            )
        },
        name="Old Disconnected Device",
        via_device=(DOMAIN, "aa:bb:cc:dd:ee:ff"),
    )

    # Try to remove disconnected device - should succeed
    result = await async_remove_config_entry_device(
        hass, mock_config_entry, disconnected_device
    )

    assert result is True


@pytest.mark.parametrize(
    ("exception", "expected_state"),
    [
        (ConnectionRefusedError, ConfigEntryState.SETUP_RETRY),
        (OpenRGBDisconnected, ConfigEntryState.SETUP_RETRY),
        (RuntimeError("Test error"), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_entry_exceptions(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_mac_address: MagicMock,
    exception: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test setup entry with various exceptions."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.openrgb.coordinator.OpenRGBClient",
        side_effect=exception,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state
