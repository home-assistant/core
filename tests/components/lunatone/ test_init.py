"""Tests for the Lunatone integration."""

from unittest.mock import AsyncMock

import aiohttp

from homeassistant.components.lunatone.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_info: AsyncMock,
    setup_integration: MockConfigEntry,
) -> None:
    """Test the Lunatone configuration entry loading/unloading."""
    config_entry = setup_integration

    assert config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.data.get(DOMAIN)
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_config_entry_not_ready(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    setup_integration: MockConfigEntry,
) -> None:
    """Test the Lunatone configuration entry not ready."""
    mock_lunatone_info.async_update.side_effect = aiohttp.ClientConnectionError()

    config_entry = setup_integration

    assert mock_lunatone_info.async_update.call_count == 1
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_config_entry_not_ready_no_data(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    setup_integration: MockConfigEntry,
) -> None:
    """Test the Lunatone configuration entry not ready."""
    mock_lunatone_info.data = None

    config_entry = setup_integration

    mock_lunatone_info.async_update.assert_called()
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_device_info(
    hass: HomeAssistant,
    base_url: str,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_info: AsyncMock,
    setup_integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device registry integration."""
    config_entry = setup_integration

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, config_entry.unique_id)}
    )
    assert device_entry is not None
    assert device_entry.manufacturer == "Lunatone"
    assert device_entry.sw_version == mock_lunatone_info.version
    assert device_entry.configuration_url == base_url


async def test_unique_id_missing(
    hass: HomeAssistant,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_info: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device registry integration."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, unique_id=None)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not device_registry.devices
