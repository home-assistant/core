"""Tests for ESPHome encryption key storage."""

from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.components.esphome.encryption_key_storage import (
    async_get_encryption_key_storage,
)
from homeassistant.core import HomeAssistant


async def test_store_and_get_key(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test storing and retrieving an encryption key."""
    storage = await async_get_encryption_key_storage(hass)

    mac_address = "AA:BB:CC:DD:EE:FF"
    key = "test_encryption_key_32_bytes_long"

    # Store the key
    await storage.async_store_key(mac_address, key)

    # Retrieve the key
    retrieved_key = await storage.async_get_key(mac_address)
    assert retrieved_key == key


async def test_store_key_case_insensitive(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test that MAC addresses are stored in lowercase."""
    storage = await async_get_encryption_key_storage(hass)

    mac_lower = "aa:bb:cc:dd:ee:ff"
    mac_upper = "AA:BB:CC:DD:EE:FF"
    key = "test_encryption_key_32_bytes_long"

    # Store with lowercase MAC
    await storage.async_store_key(mac_lower, key)

    # Should be retrievable with uppercase MAC
    retrieved_key = await storage.async_get_key(mac_upper)
    assert retrieved_key == key

    # And with lowercase MAC
    retrieved_key = await storage.async_get_key(mac_lower)
    assert retrieved_key == key


async def test_get_nonexistent_key(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test retrieving a non-existent key returns None."""
    storage = await async_get_encryption_key_storage(hass)
    result = await storage.async_get_key("11:22:33:44:55:66")
    assert result is None


async def test_remove_key(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    """Test removing an encryption key."""
    storage = await async_get_encryption_key_storage(hass)

    mac_address = "AA:BB:CC:DD:EE:FF"
    key = "test_encryption_key_32_bytes_long"

    # Store the key
    await storage.async_store_key(mac_address, key)
    assert await storage.async_get_key(mac_address) == key

    # Remove the key
    await storage.async_remove_key(mac_address)

    # Verify it's removed
    assert await storage.async_get_key(mac_address) is None


async def test_remove_nonexistent_key(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test removing a non-existent key doesn't raise an error."""
    storage = await async_get_encryption_key_storage(hass)
    # Should not raise any exception
    await storage.async_remove_key("11:22:33:44:55:66")


async def test_load_from_storage(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test loading encryption keys from storage."""
    # Prepare mock storage data
    hass_storage["esphome_encryption_keys"] = {
        "version": 1,
        "minor_version": 1,
        "key": "esphome_encryption_keys",
        "data": {
            "keys": {
                "aa:bb:cc:dd:ee:ff": "key1_32_bytes_long_for_testing!!",
                "11:22:33:44:55:66": "key2_32_bytes_long_for_testing!!",
            }
        },
    }

    # Create storage instance
    storage = await async_get_encryption_key_storage(hass)

    # Verify keys were loaded
    assert (
        await storage.async_get_key("AA:BB:CC:DD:EE:FF")
        == "key1_32_bytes_long_for_testing!!"
    )
    assert (
        await storage.async_get_key("11:22:33:44:55:66")
        == "key2_32_bytes_long_for_testing!!"
    )


async def test_save_to_storage(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test saving encryption keys to storage."""
    storage = await async_get_encryption_key_storage(hass)

    mac1 = "AA:BB:CC:DD:EE:FF"
    mac2 = "11:22:33:44:55:66"
    key1 = "key1_32_bytes_long_for_testing!!"
    key2 = "key2_32_bytes_long_for_testing!!"

    # Store keys
    await storage.async_store_key(mac1, key1)
    await storage.async_store_key(mac2, key2)

    # Verify data was saved to hass_storage
    stored_data = hass_storage["esphome_encryption_keys"]["data"]
    assert "keys" in stored_data
    assert stored_data["keys"][mac1.lower()] == key1
    assert stored_data["keys"][mac2.lower()] == key2


async def test_singleton_instance(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test that only one instance of storage exists per hass instance."""
    storage1 = await async_get_encryption_key_storage(hass)
    storage2 = await async_get_encryption_key_storage(hass)

    # Should be the same instance
    assert storage1 is storage2


async def test_concurrent_access(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test concurrent access to storage."""
    storage = await async_get_encryption_key_storage(hass)
    mac_base = "AA:BB:CC:DD:EE:"

    async def store_key(index: int) -> None:
        """Store a key with a unique MAC address."""
        mac = f"{mac_base}{index:02X}"
        key = f"key_{index}_32_bytes_long_padding!!"[:32]
        await storage.async_store_key(mac, key)

    # Store multiple keys concurrently
    await asyncio.gather(*[store_key(i) for i in range(10)])

    # Verify all keys were stored correctly
    for i in range(10):
        mac = f"{mac_base}{i:02X}"
        key = f"key_{i}_32_bytes_long_padding!!"[:32]
        retrieved = await storage.async_get_key(mac)
        assert retrieved == key


async def test_invalid_key_format(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test handling of invalid key format in storage."""
    # Prepare mock storage data with valid string keys
    hass_storage["esphome_encryption_keys"] = {
        "version": 1,
        "minor_version": 1,
        "key": "esphome_encryption_keys",
        "data": {
            "keys": {
                "aa:bb:cc:dd:ee:ff": "valid_key_32_bytes_long_padding!",
                "11:22:33:44:55:66": "another_valid_key_32_bytes_long!",
            }
        },
    }

    # Create storage instance
    storage = await async_get_encryption_key_storage(hass)

    # Keys should be retrieved correctly
    assert (
        await storage.async_get_key("AA:BB:CC:DD:EE:FF")
        == "valid_key_32_bytes_long_padding!"
    )
    assert (
        await storage.async_get_key("11:22:33:44:55:66")
        == "another_valid_key_32_bytes_long!"
    )


async def test_empty_storage(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    """Test handling of empty storage."""
    # Create storage instance with empty store
    storage = await async_get_encryption_key_storage(hass)

    # Getting any key should return None
    assert await storage.async_get_key("AA:BB:CC:DD:EE:FF") is None
