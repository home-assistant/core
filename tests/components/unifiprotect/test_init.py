"""Test the UniFi Protect setup flow."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

from pyunifiprotect import NotAuthorized, NvrError
from pyunifiprotect.data import NVR

from homeassistant.components.unifiprotect.const import CONF_DISABLE_RTSP, DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant

from . import _patch_discovery
from .conftest import MockBootstrap, MockEntityFixture

from tests.common import MockConfigEntry


async def test_setup(hass: HomeAssistant, mock_entry: MockEntityFixture):
    """Test working setup of unifiprotect entry."""

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()

    assert mock_entry.entry.state == ConfigEntryState.LOADED
    assert mock_entry.api.update.called
    assert mock_entry.entry.unique_id == mock_entry.api.bootstrap.nvr.mac


async def test_setup_multiple(
    hass: HomeAssistant,
    mock_entry: MockEntityFixture,
    mock_client,
    mock_bootstrap: MockBootstrap,
):
    """Test working setup of unifiprotect entry."""

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()

    assert mock_entry.entry.state == ConfigEntryState.LOADED
    assert mock_entry.api.update.called
    assert mock_entry.entry.unique_id == mock_entry.api.bootstrap.nvr.mac

    nvr = mock_bootstrap.nvr
    nvr._api = mock_client
    nvr.mac = "A1E00C826983"
    nvr.id
    mock_client.get_nvr = AsyncMock(return_value=nvr)

    with patch("homeassistant.components.unifiprotect.ProtectApiClient") as mock_api:
        mock_config = MockConfigEntry(
            domain=DOMAIN,
            data={
                "host": "1.1.1.1",
                "username": "test-username",
                "password": "test-password",
                "id": "UnifiProtect",
                "port": 443,
                "verify_ssl": False,
            },
            version=2,
        )
        mock_config.add_to_hass(hass)

        mock_api.return_value = mock_client

        await hass.config_entries.async_setup(mock_config.entry_id)
        await hass.async_block_till_done()

        assert mock_config.state == ConfigEntryState.LOADED
        assert mock_client.update.called
        assert mock_config.unique_id == mock_client.bootstrap.nvr.mac


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


async def test_setup_too_old(
    hass: HomeAssistant, mock_entry: MockEntityFixture, mock_old_nvr: NVR
):
    """Test setup of unifiprotect entry with too old of version of UniFi Protect."""

    mock_entry.api.get_nvr.return_value = mock_old_nvr

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


async def test_setup_starts_discovery(
    hass: HomeAssistant, mock_ufp_config_entry: ConfigEntry, mock_client
):
    """Test setting up will start discovery."""
    with _patch_discovery(), patch(
        "homeassistant.components.unifiprotect.ProtectApiClient"
    ) as mock_api:
        mock_ufp_config_entry.add_to_hass(hass)
        mock_api.return_value = mock_client
        mock_entry = MockEntityFixture(mock_ufp_config_entry, mock_client)

        await hass.config_entries.async_setup(mock_entry.entry.entry_id)
        await hass.async_block_till_done()
        assert mock_entry.entry.state == ConfigEntryState.LOADED
        await hass.async_block_till_done()
        assert len(hass.config_entries.flow.async_progress_by_handler(DOMAIN)) == 1
