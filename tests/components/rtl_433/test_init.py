"""Test the rtl_433 integration setup and unload."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from homeassistant.components.rtl_433.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rtl433_client: MagicMock,
) -> None:
    """Test a hub entry loads, registers the hub device, and unloads cleanly."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    device_registry = dr.async_get(hass)
    hub_device = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_config_entry.entry_id)}
    )
    assert hub_device is not None
    assert hub_device.manufacturer == "rtl_433"

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_rtl433_client.return_value.stop.assert_awaited()


async def test_setup_cannot_connect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rtl433_client: MagicMock,
) -> None:
    """Test the entry retries when the server never connects (test-before-setup)."""
    mock_rtl433_client.return_value.connected = False

    with patch("homeassistant.components.rtl_433.coordinator._CONNECT_TIMEOUT", 0.0):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
