"""Test the IKEA Idasen Desk init."""
from unittest.mock import AsyncMock, MagicMock

from bleak import BleakError
import pytest

from homeassistant.components.idasen_desk.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant

from . import init_integration


async def test_setup_and_shutdown(
    hass: HomeAssistant,
    mock_desk_api: MagicMock,
) -> None:
    """Test setup."""
    entry = await init_integration(hass)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED
    mock_desk_api.connect.assert_called_once()
    mock_desk_api.is_connected = True

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    mock_desk_api.disconnect.assert_called_once()


@pytest.mark.parametrize("exception", [TimeoutError(), BleakError()])
async def test_setup_connect_exception(
    hass: HomeAssistant, mock_desk_api: MagicMock, exception: Exception
) -> None:
    """Test setup with an connection exception."""
    mock_desk_api.connect = AsyncMock(side_effect=exception)
    entry = await init_integration(hass)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(hass: HomeAssistant, mock_desk_api: MagicMock) -> None:
    """Test successful unload of entry."""
    entry = await init_integration(hass)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED
    mock_desk_api.connect.assert_called_once()
    mock_desk_api.is_connected = True

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    mock_desk_api.disconnect.assert_called_once()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
