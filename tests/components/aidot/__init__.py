"""Tests for the aidot integration."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.aidot import (
    async_setup_entry,
    async_unload_entry,
    cleanup_device_registry,
)
from homeassistant.components.aidot.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_hass():
    """Fixture to create a mock HomeAssistant instance."""
    hass = AsyncMock(spec=HomeAssistant)
    hass.data = {}
    hass.config_entries = AsyncMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
    hass.bus.async_fire = AsyncMock()
    return hass


@pytest.fixture
def mock_config_entry():
    """Fixture to create a mock ConfigEntry instance."""
    return AsyncMock(
        spec=ConfigEntry,
        data={
            "device_list": ["device1", "device2"],
            "login_response": {"id": "test_id"},
            "product_list": ["product1", "product2"],
        },
    )


@patch("homeassistant.helpers.device_registry.async_get", return_value=AsyncMock())
@patch("homeassistant.components.tplink.Discover.discover")
async def test_async_setup_entry(
    mock_discover, mock_device_registry, mock_hass, mock_config_entry
) -> None:
    """Test the async_setup_entry function of the aidot integration."""
    result = await async_setup_entry(mock_hass, mock_config_entry)
    assert result is True
    assert DOMAIN in mock_hass.data
    assert "device_list" in mock_hass.data[DOMAIN]
    assert "login_response" in mock_hass.data[DOMAIN]
    assert "products" in mock_hass.data[DOMAIN]
    mock_hass.config_entries.async_forward_entry_setups.assert_called_once_with(
        mock_config_entry, [Platform.LIGHT]
    )
    mock_discover.broadcast_message.assert_called_once()


async def test_cleanup_device_registry(mock_hass) -> None:
    """Test the cleanup_device_registry function of the aidot integration."""
    device_registry_mock = AsyncMock()
    mock_hass.data = {DOMAIN: {}}
    device_registry_mock.devices.items.return_value = {
        "dev_id1": AsyncMock(identifiers={("aidot", "dev1")}),
        "dev_id2": AsyncMock(identifiers={("aidot", "dev2")}),
    }
    with patch(
        "homeassistant.helpers.device_registry.async_get",
        return_value=device_registry_mock,
    ):
        await cleanup_device_registry(mock_hass)
        device_registry_mock.async_remove_device.assert_any_call("dev_id1")
        device_registry_mock.async_remove_device.assert_any_call("dev_id2")


async def test_async_unload_entry(mock_hass, mock_config_entry) -> None:
    """Test the async_unload_entry function of the aidot integration."""
    mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    result = await async_unload_entry(mock_hass, mock_config_entry)
    assert result is True
    assert "device_list" not in mock_hass.data[DOMAIN]
    assert "login_response" not in mock_hass.data[DOMAIN]
    assert "products" not in mock_hass.data[DOMAIN]
    mock_hass.config_entries.async_unload_platforms.assert_called_once_with(
        mock_config_entry, [Platform.LIGHT]
    )
