"""Tests for Renson WAVES integration init."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.renson_waves import (
    PLATFORMS,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.components.renson_waves.coordinator import RensonWavesCoordinator
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.asyncio
async def test_async_setup_entry_success(hass: HomeAssistant) -> None:
    """Test successful setup entry."""
    entry = MockConfigEntry(
        domain="renson_waves",
        title="WAVES",
        data={CONF_HOST: "192.168.1.100", CONF_PORT: 8000},
        version=1,
    )
    mock_coordinator = AsyncMock()

    with (
        patch(
            "homeassistant.components.renson_waves.RensonWavesClient"
        ) as mock_client_class,
        patch(
            "homeassistant.components.renson_waves.RensonWavesCoordinator",
            return_value=mock_coordinator,
        ) as mock_coordinator_class,
        patch.object(hass.config_entries, "async_forward_entry_setups") as mock_forward,
    ):
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client

        result = await async_setup_entry(hass, entry)

        assert result is True
        assert entry.runtime_data is mock_coordinator
        mock_coordinator.async_config_entry_first_refresh.assert_awaited_once()
        mock_forward.assert_awaited_once_with(entry, PLATFORMS)
        mock_coordinator_class.assert_called_once()


@pytest.mark.asyncio
async def test_async_unload_entry(
    hass: HomeAssistant,
    mock_coordinator: RensonWavesCoordinator,
) -> None:
    """Test unload entry."""
    entry = MockConfigEntry(
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
        assert mock_unload.call_count == 2
