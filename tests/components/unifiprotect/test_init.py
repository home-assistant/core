"""Test the UniFi Protect setup flow."""
from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

from pyunifiprotect import NotAuthorized, NvrError

from homeassistant.components.unifiprotect.const import CONF_DISABLE_RTSP, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import MAC_ADDR, MOCK_OLD_NVR_DATA

from tests.common import MockConfigEntry


@patch("homeassistant.components.unifiprotect.ProtectApiClient")
async def test_setup(mock_api, hass: HomeAssistant, mock_client):
    """Test working setup of unifiprotect entry."""
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

    mock_api.return_value = mock_client

    await mock_config.async_setup(hass)
    await hass.async_block_till_done()

    assert mock_config.state == ConfigEntryState.LOADED
    assert mock_client.update.called
    assert mock_config.unique_id == mock_client.bootstrap.nvr.mac
    assert mock_config.entry_id in hass.data[DOMAIN]


@patch("homeassistant.components.unifiprotect.ProtectApiClient")
async def test_reload(mock_api, hass: HomeAssistant, mock_client):
    """Test updating entry reload entry."""
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

    mock_api.return_value = mock_client
    await mock_config.async_setup(hass)
    await hass.async_block_till_done()
    assert mock_config.state == ConfigEntryState.LOADED

    mock_config.add_to_hass(hass)
    options = dict(mock_config.options)
    options[CONF_DISABLE_RTSP] = True
    hass.config_entries.async_update_entry(mock_config, options=options)
    await hass.async_block_till_done()

    assert mock_config.state == ConfigEntryState.LOADED
    assert mock_config.entry_id in hass.data[DOMAIN]
    assert mock_client.async_disconnect_ws.called


@patch("homeassistant.components.unifiprotect.ProtectApiClient")
async def test_unload(mock_api, hass: HomeAssistant, mock_client):
    """Test unloading of unifiprotect entry."""
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

    mock_api.return_value = mock_client
    await mock_config.async_setup(hass)
    await hass.async_block_till_done()
    assert mock_config.state == ConfigEntryState.LOADED

    mock_config.async_unload(hass)
    assert mock_config.state == ConfigEntryState.NOT_LOADED
    assert mock_client.async_disconnect_ws.called


@patch("homeassistant.components.unifiprotect.ProtectApiClient")
async def test_setup_too_old(mock_api, hass: HomeAssistant, mock_client):
    """Test setup of unifiprotect entry with too old of version of UniFi Protect."""
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
        unique_id=dr.format_mac(MAC_ADDR),
    )

    mock_client.get_nvr.return_value = MOCK_OLD_NVR_DATA
    mock_api.return_value = mock_client

    await mock_config.async_setup(hass)
    await hass.async_block_till_done()
    assert mock_config.state == ConfigEntryState.SETUP_ERROR
    assert not mock_client.update.called


@patch("homeassistant.components.unifiprotect.ProtectApiClient")
async def test_setup_failed_update(mock_api, hass: HomeAssistant, mock_client):
    """Test setup of unifiprotect entry with failed update."""
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
        unique_id=dr.format_mac(MAC_ADDR),
    )
    mock_config.async_start_reauth = Mock()

    mock_client.update = AsyncMock(side_effect=NvrError)
    mock_api.return_value = mock_client

    await mock_config.async_setup(hass)
    await hass.async_block_till_done()
    assert mock_config.state == ConfigEntryState.SETUP_RETRY
    assert not mock_config.async_start_reauth.called
    assert mock_client.update.called


@patch("homeassistant.components.unifiprotect.ProtectApiClient")
async def test_setup_failed_update_reauth(mock_api, hass: HomeAssistant, mock_client):
    """Test setup of unifiprotect entry with update that gives unauthroized error."""
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
        unique_id=dr.format_mac(MAC_ADDR),
    )
    mock_config.async_start_reauth = Mock()

    mock_client.update = AsyncMock(side_effect=NotAuthorized)
    mock_api.return_value = mock_client

    await mock_config.async_setup(hass)
    await hass.async_block_till_done()
    assert mock_config.state == ConfigEntryState.SETUP_RETRY
    assert mock_config.async_start_reauth.called
    assert mock_client.update.called


@patch("homeassistant.components.unifiprotect.ProtectApiClient")
async def test_setup_failed_error(mock_api, hass: HomeAssistant, mock_client):
    """Test setup of unifiprotect entry with generic error."""
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
        unique_id=dr.format_mac(MAC_ADDR),
    )

    mock_client.get_nvr = AsyncMock(side_effect=NvrError)
    mock_api.return_value = mock_client

    await mock_config.async_setup(hass)
    await hass.async_block_till_done()
    assert mock_config.state == ConfigEntryState.SETUP_RETRY
    assert not mock_client.update.called


@patch("homeassistant.components.unifiprotect.ProtectApiClient")
async def test_setup_failed_auth(mock_api, hass: HomeAssistant, mock_client):
    """Test setup of unifiprotect entry with unauthorized error."""
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
        unique_id=dr.format_mac(MAC_ADDR),
    )

    mock_client.get_nvr = AsyncMock(side_effect=NotAuthorized)
    mock_api.return_value = mock_client

    await mock_config.async_setup(hass)
    assert mock_config.state == ConfigEntryState.SETUP_ERROR
    assert not mock_client.update.called
