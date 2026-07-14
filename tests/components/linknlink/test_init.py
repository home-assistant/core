"""Tests for LinknLink setup."""

from dataclasses import replace
from unittest.mock import AsyncMock

from aiolinknlink import DISPLAY_MODEL_ULTRA2, UltraConnectionError

from homeassistant.components.linknlink.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration
from .conftest import DEVICE, MAC, SESSION

from tests.common import MockConfigEntry


async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting up and unloading an entry."""
    mock_linknlink_client.connect.return_value = replace(
        SESSION, device=replace(DEVICE, model=DISPLAY_MODEL_ULTRA2)
    )
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_linknlink_client.connect.assert_awaited_once()
    mock_linknlink_client.refresh.assert_awaited_once()
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, MAC)})
    assert device is not None
    assert device.model == DISPLAY_MODEL_ULTRA2

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_retries_when_device_is_unavailable(
    hass: HomeAssistant,
    mock_linknlink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup retry when the device cannot be reached."""
    mock_linknlink_client.connect.side_effect = UltraConnectionError("offline")
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
