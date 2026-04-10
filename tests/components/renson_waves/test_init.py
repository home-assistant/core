"""Tests for Renson WAVES integration init."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.renson_waves import async_setup_entry, async_unload_entry
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant


@pytest.mark.asyncio
async def test_async_setup_entry_success(
    hass: HomeAssistant,
    mock_coordinator,
):
    """Test successful setup entry."""
    entry = ConfigEntry(
        domain="renson_waves",
        title="WAVES",
        data={CONF_HOST: "192.168.1.100", CONF_PORT: 8000},
        version=1,
    )
    entry.async_on_unload = AsyncMock()

    with (
        patch(
            "homeassistant.components.renson_waves.async_get_clientsession"
        ) as mock_session,
        patch(
            "homeassistant.components.renson_waves.RensonWavesClient"
        ) as mock_client_class,
        patch(
            "homeassistant.components.renson_waves.RensonWavesCoordinator"
        ) as mock_coordinator_class,
    ):
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_coordinator_class.return_value = mock_coordinator

        result = await async_setup_entry(hass, entry)

        assert result is True
        mock_coordinator.async_config_entry_first_refresh.assert_called_once()


@pytest.mark.asyncio
async def test_async_unload_entry(
    hass: HomeAssistant,
    mock_coordinator,
):
    """Test unload entry."""
    entry = ConfigEntry(
        domain="renson_waves",
        title="WAVES",
        data={CONF_HOST: "192.168.1.100", CONF_PORT: 8000},
        version=1,
    )
    entry.runtime_data = mock_coordinator

    with patch.object(
        hass.config_entries, "async_forward_entry_unload", return_value=True
    ) as mock_unload:
        result = await async_unload_entry(hass, entry)

        assert result is True
        mock_unload.assert_called_once()
