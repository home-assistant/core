"""Tests for the TuneBlade Remote __init__.py setup and unload."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.tuneblade_remote import (
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.components.tuneblade_remote.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


@pytest.mark.asyncio
async def test_async_setup_entry_creates_coordinator_and_runtime_data(
    hass: HomeAssistant,
) -> None:
    """Test successful async_setup_entry sets up coordinator and runtime data."""
    entry = ConfigEntry(
        domain=DOMAIN,
        data={"host": "1.2.3.4", "port": 1234},
        entry_id="test_entry",
        options={},
        version=1,
    )

    with (
        patch(
            "homeassistant.components.tuneblade_remote.async_create_clientsession"
        ) as mock_session,
        patch(
            "homeassistant.components.tuneblade_remote.TuneBladeApiClient"
        ) as mock_client_class,
        patch(
            "homeassistant.components.tuneblade_remote.TuneBladeDataUpdateCoordinator"
        ) as mock_coordinator_class,
    ):
        mock_session.return_value = AsyncMock()
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client

        mock_coordinator = AsyncMock()
        mock_coordinator.async_init = AsyncMock()
        mock_coordinator_class.return_value = mock_coordinator

        result = await async_setup_entry(hass, entry)

        # Verify async_init was called on the coordinator
        mock_coordinator.async_init.assert_awaited_once()

        # Verify hass.data updated
        assert DOMAIN in hass.data
        assert entry.entry_id in hass.data[DOMAIN]
        assert hass.data[DOMAIN][entry.entry_id] == mock_coordinator

        # Verify runtime_data is set on entry
        assert hasattr(entry, "runtime_data")
        assert entry.runtime_data.coordinator == mock_coordinator

        # Function returns True on success
        assert result is True


@pytest.mark.asyncio
async def test_async_unload_entry_removes_coordinator_and_unloads_platform(
    hass: HomeAssistant,
) -> None:
    """Test async_unload_entry calls platform unload and removes coordinator from hass.data."""
    entry = ConfigEntry(
        domain=DOMAIN,
        data={"host": "1.2.3.4", "port": 1234},
        entry_id="test_entry",
        options={},
        version=1,
    )

    # Setup hass.data with a dummy coordinator
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = object()

    with patch.object(
        hass.config_entries, "async_unload_platforms", return_value=AsyncMock()
    ) as mock_unload_platforms:
        # async_unload_platforms returns True
        mock_unload_platforms.return_value = True

        result = await async_unload_entry(hass, entry)

        # Verify unload called with correct parameters
        mock_unload_platforms.assert_awaited_once_with(entry, ["media_player"])

        # Coordinator removed from hass.data
        assert entry.entry_id not in hass.data[DOMAIN]

        # Result True indicates unload success
        assert result is True


@pytest.mark.asyncio
async def test_async_unload_entry_platform_unload_fails_keeps_coordinator(
    hass: HomeAssistant,
) -> None:
    """Test async_unload_entry keeps coordinator if platform unload fails."""
    entry = ConfigEntry(
        domain=DOMAIN,
        data={"host": "1.2.3.4", "port": 1234},
        entry_id="test_entry",
        options={},
        version=1,
    )

    # Setup hass.data with a dummy coordinator
    coordinator = object()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    with patch.object(
        hass.config_entries, "async_unload_platforms", return_value=AsyncMock()
    ) as mock_unload_platforms:
        # async_unload_platforms returns False (failure)
        mock_unload_platforms.return_value = False

        result = await async_unload_entry(hass, entry)

        mock_unload_platforms.assert_awaited_once_with(entry, ["media_player"])

        # Coordinator should still be present in hass.data
        assert hass.data[DOMAIN][entry.entry_id] is coordinator

        # Result False indicates unload failure
        assert result is False
