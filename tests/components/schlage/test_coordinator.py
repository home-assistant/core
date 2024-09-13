"""Test schlage DataUpdateCoordinator."""

from typing import Any
from unittest.mock import Mock, create_autospec

from freezegun.api import FrozenDateTimeFactory
from pyschlage.lock import Lock

from homeassistant.components.schlage.const import DOMAIN, UPDATE_INTERVAL
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceRegistry

from tests.common import async_fire_time_changed


async def test_lock_device_registry(
    hass: HomeAssistant,
    device_registry: DeviceRegistry,
    mock_added_config_entry: ConfigEntry,
) -> None:
    """Test lock is added to device registry."""
    device = device_registry.async_get_device(identifiers={(DOMAIN, "test")})
    assert device.model == "<model-name>"
    assert device.sw_version == "1.0"
    assert device.name == "Vault Door"
    assert device.manufacturer == "Schlage"


async def test_auto_add_device(
    hass: HomeAssistant,
    device_registry: DeviceRegistry,
    mock_added_config_entry: ConfigEntry,
    mock_schlage: Mock,
    mock_lock: Mock,
    mock_lock_attrs: dict[str, Any],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test new devices are auto-added to the device registry."""
    device = device_registry.async_get_device(identifiers={(DOMAIN, "test")})
    assert device is not None

    mock_lock_attrs["device_id"] = "test2"
    new_mock_lock = create_autospec(Lock)
    new_mock_lock.configure_mock(**mock_lock_attrs)
    mock_schlage.locks.return_value = [mock_lock, new_mock_lock]

    # Make the coordinator refresh data.
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    new_device = device_registry.async_get_device(identifiers={(DOMAIN, "test2")})
    assert new_device is not None


async def test_auto_remove_device(
    hass: HomeAssistant,
    device_registry: DeviceRegistry,
    mock_added_config_entry: ConfigEntry,
    mock_schlage: Mock,
    mock_lock: Mock,
    mock_lock_attrs: dict[str, Any],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test new devices are auto-added to the device registry."""
    device = device_registry.async_get_device(identifiers={(DOMAIN, "test")})
    assert device is not None

    mock_schlage.locks.return_value = []

    # Make the coordinator refresh data.
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    new_device = device_registry.async_get_device(identifiers={(DOMAIN, "test")})
    assert new_device is None
