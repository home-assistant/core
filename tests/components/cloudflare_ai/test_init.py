"""Tests for the Cloudflare Workers AI integration setup."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.components.cloudflare_ai.client import (
    CloudflareAIAuthError,
    CloudflareAIConnectionError,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_validate_credentials: AsyncMock,
    setup_ha_components: None,
) -> None:
    """Test successful setup of a config entry."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is not None


async def test_setup_entry_auth_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    setup_ha_components: None,
) -> None:
    """Test setup fails with ConfigEntryAuthFailed on auth error."""
    with patch(
        "homeassistant.components.cloudflare_ai.client.CloudflareAIClient.validate_credentials",
        new_callable=AsyncMock,
        side_effect=CloudflareAIAuthError("Invalid token"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    setup_ha_components: None,
) -> None:
    """Test setup retries with ConfigEntryNotReady on connection error."""
    with patch(
        "homeassistant.components.cloudflare_ai.client.CloudflareAIClient.validate_credentials",
        new_callable=AsyncMock,
        side_effect=CloudflareAIConnectionError("Connection failed"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_validate_credentials: AsyncMock,
    setup_ha_components: None,
) -> None:
    """Test unloading a config entry."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
