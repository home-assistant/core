"""Tests for the Glutz eAccess integration setup."""
from __future__ import annotations

from unittest.mock import AsyncMock

from pyglutz_eaccess import GlutzAuthError, GlutzConnectionError

from homeassistant.components.glutz_eaccess import async_remove_config_entry_device
from homeassistant.components.glutz_eaccess.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_glutz_client: AsyncMock,
) -> None:
    """Test successful setup of a config entry."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_glutz_client: AsyncMock,
) -> None:
    """Test unloading a config entry."""
    await setup_integration(hass, mock_config_entry)

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_reload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_glutz_client: AsyncMock,
) -> None:
    """Test reloading a config entry ends up LOADED."""
    await setup_integration(hass, mock_config_entry)

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_setup_auth_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_glutz_client: AsyncMock,
) -> None:
    """Test that an auth error during first refresh puts entry in AUTH_ERROR state."""
    mock_glutz_client.get_access_points.side_effect = GlutzAuthError

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_glutz_client: AsyncMock,
) -> None:
    """Test that a connection error during first refresh puts entry in SETUP_RETRY."""
    mock_glutz_client.get_access_points.side_effect = GlutzConnectionError

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_remove_config_entry_device_unknown(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_glutz_client: AsyncMock,
) -> None:
    """Test that removal is allowed for a device not in coordinator data."""
    await setup_integration(hass, mock_config_entry)

    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "ap-999")},
    )

    assert await async_remove_config_entry_device(hass, mock_config_entry, device_entry)


async def test_remove_config_entry_device_known(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_glutz_client: AsyncMock,
) -> None:
    """Test that removal is blocked for a device still in coordinator data."""
    await setup_integration(hass, mock_config_entry)

    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "ap-1")},
    )

    assert not await async_remove_config_entry_device(
        hass, mock_config_entry, device_entry
    )
