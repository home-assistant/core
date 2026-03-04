"""Test BLE device name sync for the Flic Button integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.flic_button.const import DOMAIN
from homeassistant.components.flic_button.coordinator import FlicCoordinator
from homeassistant.components.flic_button.handlers.base import DeviceProtocolHandler
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import FLIC2_ADDRESS

from tests.common import MockConfigEntry


@pytest.fixture
def platforms() -> list[Platform]:
    """Return list of platforms to test."""
    return [Platform.SENSOR]


async def test_name_read_on_reconnect_sets_name_by_user(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_flic_client: MagicMock,
    mock_ble_device_from_address: MagicMock,
) -> None:
    """Test that device name from BLE sets name_by_user on reconnect."""
    # First connect returns empty name (device registry not created yet anyway)
    mock_flic_client.get_name = AsyncMock(return_value=("", 0))

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

    # Simulate reconnect with device returning a name
    mock_flic_client.get_name = AsyncMock(return_value=("My Flic", 1000))
    coordinator: FlicCoordinator = mock_config_entry.runtime_data
    coordinator._connected = False
    await coordinator.async_connect()
    await hass.async_block_till_done()

    device = device_registry.async_get_device(identifiers={(DOMAIN, FLIC2_ADDRESS)})
    assert device is not None
    assert device.name_by_user == "My Flic"


async def test_name_read_on_reconnect_does_not_overwrite_existing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_flic_client: MagicMock,
    mock_ble_device_from_address: MagicMock,
) -> None:
    """Test that device name from BLE does NOT overwrite existing name_by_user."""
    mock_flic_client.get_name = AsyncMock(return_value=("", 0))

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
    mock_flic_client.get_name = AsyncMock(return_value=("Device Name", 1000))
    coordinator: FlicCoordinator = mock_config_entry.runtime_data
    coordinator._connected = False
    await coordinator.async_connect()
    await hass.async_block_till_done()

    device = device_registry.async_get_device(identifiers={(DOMAIN, FLIC2_ADDRESS)})
    assert device is not None
    assert device.name_by_user == "User Custom Name"


async def test_name_read_empty_string_no_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_flic_client: MagicMock,
    mock_ble_device_from_address: MagicMock,
) -> None:
    """Test that empty device name does not set name_by_user."""
    mock_flic_client.get_name = AsyncMock(return_value=("", 0))

    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.flic_button.FlicClient",
        return_value=mock_flic_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Reconnect with empty name
    coordinator: FlicCoordinator = mock_config_entry.runtime_data
    coordinator._connected = False
    await coordinator.async_connect()
    await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(identifiers={(DOMAIN, FLIC2_ADDRESS)})
    assert device is not None
    assert device.name_by_user is None


async def test_name_read_failure_connection_succeeds(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_flic_client: MagicMock,
    mock_ble_device_from_address: MagicMock,
) -> None:
    """Test that name read failure does not prevent connection."""
    mock_flic_client.get_name = AsyncMock(side_effect=TimeoutError("timeout"))

    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.flic_button.FlicClient",
        return_value=mock_flic_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    coordinator: FlicCoordinator = mock_config_entry.runtime_data
    assert coordinator.connected is True


async def test_ha_rename_pushes_to_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_flic_client: MagicMock,
    mock_ble_device_from_address: MagicMock,
) -> None:
    """Test that renaming device in HA pushes name to physical device."""
    mock_flic_client.get_name = AsyncMock(return_value=("", 0))
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
    mock_flic_client.get_name = AsyncMock(return_value=("", 0))

    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.flic_button.FlicClient",
        return_value=mock_flic_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Simulate disconnection
    coordinator: FlicCoordinator = mock_config_entry.runtime_data
    coordinator._connected = False
    mock_flic_client.is_connected = False

    # Rename device in HA - should not crash
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(identifiers={(DOMAIN, FLIC2_ADDRESS)})
    assert device is not None

    device_registry.async_update_device(device.id, name_by_user="Offline Name")
    await hass.async_block_till_done()

    # set_name should NOT have been called
    mock_flic_client.set_name.assert_not_called()


def test_truncate_name_bytes_short_name() -> None:
    """Test truncation with a name that fits within 23 bytes."""
    result = DeviceProtocolHandler._truncate_name_bytes("Hello")
    assert result == b"Hello"
    assert len(result) <= 23


def test_truncate_name_bytes_exact_limit() -> None:
    """Test truncation with a name exactly at 23 bytes."""
    name = "a" * 23
    result = DeviceProtocolHandler._truncate_name_bytes(name)
    assert result == name.encode("utf-8")
    assert len(result) == 23


def test_truncate_name_bytes_over_limit() -> None:
    """Test truncation with a name exceeding 23 bytes."""
    name = "a" * 30
    result = DeviceProtocolHandler._truncate_name_bytes(name)
    assert len(result) == 23
    assert result == b"a" * 23


def test_truncate_name_bytes_multibyte_boundary() -> None:
    """Test truncation at UTF-8 character boundary for multibyte chars."""
    # Each emoji is 4 bytes, so 6 emojis = 24 bytes, exceeds 23
    # Should truncate to 5 emojis (20 bytes), not split a character
    name = "\U0001f600" * 6  # 6 grinning face emojis
    result = DeviceProtocolHandler._truncate_name_bytes(name)
    assert len(result) <= 23
    # Should be valid UTF-8
    decoded = result.decode("utf-8")
    assert len(decoded) == 5  # 5 complete emojis (20 bytes)


def test_truncate_name_bytes_mixed_multibyte() -> None:
    """Test truncation with mixed single and multibyte characters."""
    # 20 ASCII chars + 1 emoji (4 bytes) = 24 bytes total
    name = "a" * 20 + "\U0001f600"
    result = DeviceProtocolHandler._truncate_name_bytes(name)
    assert len(result) <= 23
    # Should keep 20 'a' chars but drop the emoji that would exceed 23 bytes
    decoded = result.decode("utf-8")
    assert decoded == "a" * 20
