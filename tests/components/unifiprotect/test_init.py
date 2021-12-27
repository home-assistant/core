"""Test the UniFi Protect setup flow."""
from __future__ import annotations

from unittest.mock import AsyncMock

from pyunifiprotect import NotAuthorized, NvrError

from homeassistant.components.unifiprotect.const import CONF_DISABLE_RTSP
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import MOCK_OLD_NVR_DATA, MockEntityFixture


async def test_setup(hass: HomeAssistant, mock_entry: MockEntityFixture):
    """Test working setup of unifiprotect entry."""

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()

    assert mock_entry.entry.state == ConfigEntryState.LOADED
    assert mock_entry.api.update.called
    assert mock_entry.entry.unique_id == mock_entry.api.bootstrap.nvr.mac


async def test_reload(hass: HomeAssistant, mock_entry: MockEntityFixture):
    """Test updating entry reload entry."""

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()
    assert mock_entry.entry.state == ConfigEntryState.LOADED

    options = dict(mock_entry.entry.options)
    options[CONF_DISABLE_RTSP] = True
    hass.config_entries.async_update_entry(mock_entry.entry, options=options)
    await hass.async_block_till_done()

    assert mock_entry.entry.state == ConfigEntryState.LOADED
    assert mock_entry.api.async_disconnect_ws.called


async def test_unload(hass: HomeAssistant, mock_entry: MockEntityFixture):
    """Test unloading of unifiprotect entry."""

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()
    assert mock_entry.entry.state == ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_entry.entry.entry_id)
    assert mock_entry.entry.state == ConfigEntryState.NOT_LOADED
    assert mock_entry.api.async_disconnect_ws.called


async def test_setup_too_old(hass: HomeAssistant, mock_entry: MockEntityFixture):
    """Test setup of unifiprotect entry with too old of version of UniFi Protect."""

    mock_entry.api.get_nvr.return_value = MOCK_OLD_NVR_DATA

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()
    assert mock_entry.entry.state == ConfigEntryState.SETUP_ERROR
    assert not mock_entry.api.update.called


async def test_setup_failed_update(hass: HomeAssistant, mock_entry: MockEntityFixture):
    """Test setup of unifiprotect entry with failed update."""

    mock_entry.api.update = AsyncMock(side_effect=NvrError)

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()
    assert mock_entry.entry.state == ConfigEntryState.SETUP_RETRY
    assert mock_entry.api.update.called


async def test_setup_failed_update_reauth(
    hass: HomeAssistant, mock_entry: MockEntityFixture
):
    """Test setup of unifiprotect entry with update that gives unauthroized error."""

    mock_entry.api.update = AsyncMock(side_effect=NotAuthorized)

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()
    assert mock_entry.entry.state == ConfigEntryState.SETUP_RETRY
    assert mock_entry.api.update.called


async def test_setup_failed_error(hass: HomeAssistant, mock_entry: MockEntityFixture):
    """Test setup of unifiprotect entry with generic error."""

    mock_entry.api.get_nvr = AsyncMock(side_effect=NvrError)

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()
    assert mock_entry.entry.state == ConfigEntryState.SETUP_RETRY
    assert not mock_entry.api.update.called


async def test_setup_failed_auth(hass: HomeAssistant, mock_entry: MockEntityFixture):
    """Test setup of unifiprotect entry with unauthorized error."""

    mock_entry.api.get_nvr = AsyncMock(side_effect=NotAuthorized)

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    assert mock_entry.entry.state == ConfigEntryState.SETUP_ERROR
    assert not mock_entry.api.update.called
