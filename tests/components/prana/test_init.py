"""Tests for Prana integration entry points (async_setup_entry / async_unload_entry)."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.prana import (
    PLATFORMS,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.components.prana.const import DOMAIN
from homeassistant.components.prana.coordinator import PranaCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import async_init_integration


@pytest.mark.asyncio
async def test_async_setup_entry_creates_coordinator_and_forwards(
    hass: HomeAssistant, mock_config_entry, mock_prana_api
) -> None:
    """async_setup_entry should create coordinator, refresh it, store runtime_data and forward setups."""

    hass.config_entries.async_forward_entry_setups = AsyncMock()

    result = await async_setup_entry(hass, mock_config_entry)

    assert result is True

    assert isinstance(mock_config_entry.runtime_data, PranaCoordinator)

    mock_prana_api.get_device_info.assert_awaited()

    hass.config_entries.async_forward_entry_setups.assert_awaited_with(
        mock_config_entry, PLATFORMS
    )


@pytest.mark.asyncio
async def test_async_unload_entry_unloads_platforms(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """async_unload_entry should forward to hass.config_entries.async_unload_platforms and return its result."""

    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

    result = await async_unload_entry(hass, mock_config_entry)

    assert result is True
    hass.config_entries.async_unload_platforms.assert_awaited_with(
        mock_config_entry, PLATFORMS
    )


@pytest.mark.asyncio
async def test_device_info_registered(
    hass: HomeAssistant,
    mock_config_entry,
    mock_prana_api,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Device info from the API should be registered on the device registry."""
    await async_init_integration(hass, mock_config_entry)

    device_info = mock_prana_api.get_device_info.return_value

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_config_entry.entry_id)}
    )
    assert device is not None

    assert device.serial_number == device_info.manufactureId
    assert device.name == device_info.label
    assert device.model == device_info.pranaModel
    assert device.sw_version == str(device_info.fwVersion)
