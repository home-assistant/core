"""Test BLE device name sync for the Flic Button integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.flic_button.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import FLIC2_ADDRESS

from tests.common import MockConfigEntry


@pytest.fixture
def platforms() -> list[Platform]:
    """Return list of platforms to test."""
    return [Platform.EVENT]


async def test_name_sync_on_connect_sets_name_by_user(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_flic_client: MagicMock,
    mock_ble_device_from_address: MagicMock,
) -> None:
    """Test that device name from BLE sets name_by_user on connect via state callback."""
    # State callback will be registered; we capture it to simulate state changes
    state_callbacks: list = []

    def capture_state_callback(cb):
        state_callbacks.append(cb)
        return lambda: None

    mock_flic_client.register_state_callback = MagicMock(
        side_effect=capture_state_callback
    )

    # First connect returns no name
    mock_flic_client.state.device_name = None

    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.flic_button.FlicClient",
        return_value=mock_flic_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Device now exists in registry with no name_by_user
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(identifiers={(DOMAIN, FLIC2_ADDRESS)})
    assert device is not None
    assert device.name_by_user is None

    # Simulate reconnect with device returning a name via state callback
    mock_flic_client.state.connected = True
    mock_flic_client.state.device_name = "My Flic"
    mock_flic_client.state.firmware_version = 10

    # Fire state callbacks (simulating what the library does on reconnect)
    for cb in state_callbacks:
        cb(mock_flic_client.state)
    await hass.async_block_till_done()

    device = device_registry.async_get_device(identifiers={(DOMAIN, FLIC2_ADDRESS)})
    assert device is not None
    assert device.name_by_user == "My Flic"


async def test_name_sync_does_not_overwrite_existing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_flic_client: MagicMock,
    mock_ble_device_from_address: MagicMock,
) -> None:
    """Test that device name from BLE does NOT overwrite existing name_by_user."""
    state_callbacks: list = []

    def capture_state_callback(cb):
        state_callbacks.append(cb)
        return lambda: None

    mock_flic_client.register_state_callback = MagicMock(
        side_effect=capture_state_callback
    )
    mock_flic_client.state.device_name = None

    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.flic_button.FlicClient",
        return_value=mock_flic_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Set name_by_user manually
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(identifiers={(DOMAIN, FLIC2_ADDRESS)})
    assert device is not None
    device_registry.async_update_device(device.id, name_by_user="User Custom Name")

    # Simulate reconnect with device returning a different name
    mock_flic_client.state.connected = True
    mock_flic_client.state.device_name = "Device Name"
    mock_flic_client.state.firmware_version = 10
    for cb in state_callbacks:
        cb(mock_flic_client.state)
    await hass.async_block_till_done()

    device = device_registry.async_get_device(identifiers={(DOMAIN, FLIC2_ADDRESS)})
    assert device is not None
    assert device.name_by_user == "User Custom Name"


async def test_name_sync_empty_string_no_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_flic_client: MagicMock,
    mock_ble_device_from_address: MagicMock,
) -> None:
    """Test that empty device name does not set name_by_user."""
    state_callbacks: list = []

    def capture_state_callback(cb):
        state_callbacks.append(cb)
        return lambda: None

    mock_flic_client.register_state_callback = MagicMock(
        side_effect=capture_state_callback
    )
    mock_flic_client.state.device_name = None

    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.flic_button.FlicClient",
        return_value=mock_flic_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Simulate reconnect with empty name
    mock_flic_client.state.connected = True
    mock_flic_client.state.device_name = ""
    for cb in state_callbacks:
        cb(mock_flic_client.state)
    await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(identifiers={(DOMAIN, FLIC2_ADDRESS)})
    assert device is not None
    assert device.name_by_user is None


async def test_ha_rename_pushes_to_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_flic_client: MagicMock,
    mock_ble_device_from_address: MagicMock,
) -> None:
    """Test that renaming device in HA pushes name to physical device."""
    mock_flic_client.state.device_name = None
    mock_flic_client.set_name = AsyncMock(return_value=("New Name", 1000))

    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.flic_button.FlicClient",
        return_value=mock_flic_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Rename device in HA
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(identifiers={(DOMAIN, FLIC2_ADDRESS)})
    assert device is not None

    device_registry.async_update_device(device.id, name_by_user="New Name")
    await hass.async_block_till_done()

    mock_flic_client.set_name.assert_called_once_with("New Name")


async def test_ha_rename_while_disconnected_no_crash(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_flic_client: MagicMock,
    mock_ble_device_from_address: MagicMock,
) -> None:
    """Test that renaming device while disconnected does not crash."""
    mock_flic_client.state.device_name = None

    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.flic_button.FlicClient",
        return_value=mock_flic_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Simulate disconnection
    mock_flic_client.state.connected = False
    mock_flic_client.is_connected = False

    # Rename device in HA - should not crash
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(identifiers={(DOMAIN, FLIC2_ADDRESS)})
    assert device is not None

    device_registry.async_update_device(device.id, name_by_user="Offline Name")
    await hass.async_block_till_done()

    # set_name should NOT have been called
    mock_flic_client.set_name.assert_not_called()
