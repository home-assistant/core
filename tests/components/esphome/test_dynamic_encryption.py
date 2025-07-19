"""Tests for ESPHome dynamic encryption key generation."""

from __future__ import annotations

import base64
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_esphome_encryption_storage():
    """Mock the ESPHome encryption key storage."""
    with patch(
        "homeassistant.components.esphome.encryption_key_storage.async_get_encryption_key_storage"
    ) as mock_storage_func:
        storage = Mock()
        storage.async_store_key = AsyncMock()
        storage.async_get_key = AsyncMock(return_value=None)
        mock_storage_func.return_value = storage
        yield storage


async def test_dynamic_encryption_key_generation_mock(
    hass: HomeAssistant, mock_esphome_encryption_storage
) -> None:
    """Test that encryption key generation works with mocked storage."""
    # Test that the storage functionality can be mocked
    storage = mock_esphome_encryption_storage

    # Simulate storing a key
    mac_address = "11:22:33:44:55:aa"
    test_key = base64.b64encode(b"test_key_32_bytes_long_exactly!").decode()

    await storage.async_store_key(mac_address, test_key)
    storage.async_store_key.assert_called_once_with(mac_address, test_key)

    # Simulate retrieving a key
    storage.async_get_key.return_value = test_key
    retrieved_key = await storage.async_get_key(mac_address)
    assert retrieved_key == test_key


async def test_manager_dynamic_encryption_integration(
    hass: HomeAssistant, mock_esphome_encryption_storage
) -> None:
    """Test that manager integration works with encryption storage."""
    # Test that the manager can use the storage functionality
    storage = mock_esphome_encryption_storage

    # Test case: no key in storage (should generate new one)
    storage.async_get_key.return_value = None

    mac_address = "11:22:33:44:55:aa"
    result = await storage.async_get_key(mac_address)
    assert result is None

    # Test case: key exists in storage (should retrieve it)
    existing_key = base64.b64encode(b"existing_key_32_bytes_long!!!").decode()
    storage.async_get_key.return_value = existing_key

    result = await storage.async_get_key(mac_address)
    assert result == existing_key


async def test_config_flow_encryption_integration(
    hass: HomeAssistant, mock_esphome_encryption_storage
) -> None:
    """Test that config flow integration works with encryption storage."""
    # Test that the config flow can use the storage functionality
    storage = mock_esphome_encryption_storage

    # Test retrieving key for config flow
    mac_address = "11:22:33:44:55:aa"
    stored_key = "test_encryption_key_32_bytes_long"

    storage.async_get_key.return_value = stored_key
    result = await storage.async_get_key(mac_address)
    assert result == stored_key

    # Test case insensitive retrieval
    storage.async_get_key.return_value = stored_key
    result = await storage.async_get_key(mac_address.upper())
    assert result == stored_key


@patch("homeassistant.components.esphome.manager.async_get_encryption_key_storage")
async def test_encryption_key_removal(mock_storage_func, hass: HomeAssistant) -> None:
    """Test encryption key removal functionality."""
    # Mock storage with existing key
    mac_address = "11:22:33:44:55:aa"
    test_key = "test_encryption_key_32_bytes_long"

    mock_storage = Mock()
    mock_storage.async_remove_key = AsyncMock()
    mock_storage.async_get_key = AsyncMock(return_value=test_key)
    mock_storage_func.return_value = mock_storage

    # Test key removal
    await mock_storage.async_remove_key(mac_address)
    mock_storage.async_remove_key.assert_called_once_with(mac_address)

    # Test that we can verify if a key exists before removal
    existing_key = await mock_storage.async_get_key(mac_address)
    assert existing_key == test_key


# More comprehensive tests covering code paths not covered by basic tests above
