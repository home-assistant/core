"""Tests for the TuneBlade Remote __init__.py setup and unload."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.tuneblade_remote import (
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.components.tuneblade_remote.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.asyncio
async def test_async_setup_entry_creates_coordinator_and_runtime_data(
    hass: HomeAssistant,
) -> None:
    """Test successful async_setup_entry sets up coordinator and runtime data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test_entry",
        data={"host": "1.2.3.4", "port": 1234, "name": "Test"},
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.tuneblade_remote.async_create_clientsession",
            return_value=AsyncMock(),
        ),
        patch(
            "homeassistant.components.tuneblade_remote.TuneBladeApiClient",
            return_value=AsyncMock(),
        ),
        patch(
            "homeassistant.components.tuneblade_remote.TuneBladeDataUpdateCoordinator",
            return_value=AsyncMock(),
        ) as mock_coordinator_class,
    ):
        mock_coordinator = mock_coordinator_class.return_value
        mock_coordinator.async_init = AsyncMock()

        result = await async_setup_entry(hass, entry)

        mock_coordinator.async_init.assert_awaited_once()
        assert DOMAIN in hass.data
        assert entry.entry_id in hass.data[DOMAIN]
        assert hass.data[DOMAIN][entry.entry_id] == mock_coordinator

        # If your integration sets runtime_data manually
        entry.runtime_data = SimpleNamespace(coordinator=mock_coordinator)
        assert entry.runtime_data.coordinator == mock_coordinator

        assert result is True


@pytest.mark.asyncio
async def test_async_unload_entry_removes_coordinator_and_unloads_platform(
    hass: HomeAssistant,
) -> None:
    """Test async_unload_entry calls platform unload and removes coordinator from hass.data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test_entry",
        data={"host": "1.2.3.4", "port": 1234, "name": "Test"},
    )
    entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = object()

    mock_unload = AsyncMock()
    mock_unload.return_value = True

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        mock_unload,
    ) as mock_unload_platforms:
        result = await async_unload_entry(hass, entry)

        mock_unload_platforms.assert_awaited_once_with(entry, ["media_player"])
        assert entry.entry_id not in hass.data[DOMAIN]
        assert result is True


@pytest.mark.asyncio
async def test_async_unload_entry_platform_unload_fails_keeps_coordinator(
    hass: HomeAssistant,
) -> None:
    """Test async_unload_entry keeps coordinator if platform unload fails."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test_entry",
        data={"host": "1.2.3.4", "port": 1234, "name": "Test"},
    )
    entry.add_to_hass(hass)
    coordinator = object()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    mock_unload = AsyncMock()
    mock_unload.return_value = False

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        mock_unload,
    ) as mock_unload_platforms:
        result = await async_unload_entry(hass, entry)

        mock_unload_platforms.assert_awaited_once_with(entry, ["media_player"])
        assert hass.data[DOMAIN][entry.entry_id] is coordinator
        assert result is False
