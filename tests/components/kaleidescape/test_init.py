"""Tests for Kaleidescape config entry."""

from unittest.mock import AsyncMock

from homeassistant.components.kaleidescape.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import MOCK_SERIAL

from tests.common import MockConfigEntry


async def test_unload_config_entry(
    hass: HomeAssistant,
    mock_device: AsyncMock,
    mock_integration: MockConfigEntry,
) -> None:
    """Test config entry loading and unloading."""
    mock_config_entry = mock_integration
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_device.connect.call_count == 1
    assert mock_device.disconnect.call_count == 0

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_device.disconnect.call_count == 1
    assert mock_config_entry.entry_id not in hass.data[DOMAIN]


async def test_config_entry_not_ready(
    hass: HomeAssistant,
    mock_device: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test config entry not ready."""
    mock_device.connect.side_effect = ConnectionError

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_device: AsyncMock,
    mock_integration: MockConfigEntry,
) -> None:
    """Test device."""
    device = device_registry.async_get_device(
        identifiers={("kaleidescape", MOCK_SERIAL)}
    )
    assert device is not None
    assert device.identifiers == {("kaleidescape", MOCK_SERIAL)}
