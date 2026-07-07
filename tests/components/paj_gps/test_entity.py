"""Tests for the PAJ GPS base entity."""

from __future__ import annotations

from unittest.mock import AsyncMock

from pajgps_api.models.device import Device

from homeassistant.components.paj_gps.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry


async def test_entity_device_info(
    hass: HomeAssistant,
    mock_paj_gps_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that device info is correctly set up."""
    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device(identifiers={(DOMAIN, "42_1")})
    assert device is not None
    assert device.name == "Device 1"
    assert device.manufacturer == "PAJ GPS"
    assert device.model is None


async def test_entity_device_info_with_model(
    hass: HomeAssistant,
    mock_paj_gps_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that device model is populated when device_models is present."""
    mock_paj_gps_api.get_devices.return_value = [
        Device(
            id=1,
            name="Device 1",
            device_models=[{"model": "ALLROUND Finder 4G"}],
        )
    ]

    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device(identifiers={(DOMAIN, "42_1")})
    assert device is not None
    assert device.model == "ALLROUND Finder 4G"


async def test_entity_device_info_fallback_name(
    hass: HomeAssistant,
    mock_paj_gps_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that device name falls back to 'PAJ GPS <id>' when name is absent."""
    mock_paj_gps_api.get_devices.return_value = [
        Device(id=1, name=None, device_models=[])
    ]

    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device(identifiers={(DOMAIN, "42_1")})
    assert device is not None
    assert device.name == "PAJ GPS 1"


async def test_entity_device_info_non_dict_device_models(
    hass: HomeAssistant,
    mock_paj_gps_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that model is None when device_models entries are not dicts."""
    mock_paj_gps_api.get_devices.return_value = [
        Device(id=1, name="Device 1", device_models=[100])
    ]

    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device(identifiers={(DOMAIN, "42_1")})
    assert device is not None
    assert device.model is None
