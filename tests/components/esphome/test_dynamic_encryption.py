"""Tests for ESPHome dynamic encryption key generation."""

from __future__ import annotations

import base64

from homeassistant.components.esphome.encryption_key_storage import (
    ESPHomeEncryptionKeyStorage,
    async_get_encryption_key_storage,
)
from homeassistant.core import HomeAssistant


async def test_dynamic_encryption_key_generation_mock(hass: HomeAssistant) -> None:
    """Test that encryption key generation works with mocked storage."""
    storage = await async_get_encryption_key_storage(hass)

    # Store a key
    mac_address = "11:22:33:44:55:aa"
    test_key = base64.b64encode(b"test_key_32_bytes_long_exactly!").decode()

    await storage.async_store_key(mac_address, test_key)

    # Retrieve a key
    retrieved_key = await storage.async_get_key(mac_address)
    assert retrieved_key == test_key


async def test_encryption_key_storage_remove_key(hass: HomeAssistant) -> None:
    """Test ESPHomeEncryptionKeyStorage async_remove_key method."""
    # Create storage instance
    storage = ESPHomeEncryptionKeyStorage(hass)

    # Test removing a key that exists
    mac_address = "11:22:33:44:55:aa"
    test_key = "test_encryption_key_32_bytes_long"

    # First store a key
    await storage.async_store_key(mac_address, test_key)

    # Verify key exists
    retrieved_key = await storage.async_get_key(mac_address)
    assert retrieved_key == test_key

    # Remove the key
    await storage.async_remove_key(mac_address)

    # Verify key no longer exists
    retrieved_key = await storage.async_get_key(mac_address)
    assert retrieved_key is None

    # Test removing a key that doesn't exist (should not raise an error)
    non_existent_mac = "aa:bb:cc:dd:ee:ff"
    await storage.async_remove_key(non_existent_mac)  # Should not raise

    # Test case insensitive removal
    upper_mac = "22:33:44:55:66:77"
    await storage.async_store_key(upper_mac, test_key)

    # Remove using lowercase MAC address
    await storage.async_remove_key(upper_mac.lower())

    # Verify key was removed
    retrieved_key = await storage.async_get_key(upper_mac)
    assert retrieved_key is None


async def test_encryption_key_basic_storage(
    hass: HomeAssistant,
) -> None:
    """Test basic encryption key storage functionality."""
    storage = await async_get_encryption_key_storage(hass)
    mac_address = "11:22:33:44:55:aa"
    key = "test_encryption_key_32_bytes_long"

    # Store key
    await storage.async_store_key(mac_address, key)

    # Retrieve key
    retrieved_key = await storage.async_get_key(mac_address)
    assert retrieved_key == key


async def test_retrieve_key_from_storage(
    hass: HomeAssistant,
) -> None:
    """Test config flow can retrieve encryption key from storage for new device."""
    # Test that the encryption key storage integration works with config flow
    storage = await async_get_encryption_key_storage(hass)
    mac_address = "11:22:33:44:55:aa"
    stored_key = "test_encryption_key_32_bytes_long"

    # Store encryption key for a device
    await storage.async_store_key(mac_address, stored_key)

    # Verify the key can be retrieved (simulating config flow behavior)
    retrieved_key = await storage.async_get_key(mac_address)
    assert retrieved_key == stored_key

    # Test case insensitive retrieval (since config flows might use different case)
    retrieved_key_upper = await storage.async_get_key(mac_address.upper())
    assert retrieved_key_upper == stored_key
