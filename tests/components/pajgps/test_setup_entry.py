"""Unit tests for __init__.py async_setup_entry.

Coverage:
- cannot_connect → raises ConfigEntryNotReady before coordinator is created
- invalid_auth   → raises ConfigEntryNotReady before coordinator is created
- valid credentials + coordinator success → returns True, runtime_data set
- valid credentials + coordinator first-refresh fails → raises ConfigEntryNotReady
"""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.pajgps import (
    _async_update_listener,
    async_remove_config_entry_device,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.exceptions import ConfigEntryNotReady


def _make_mock_entry(
    email: str = "user@example.com", password: str = "secret"
) -> MagicMock:
    """Return a minimal mock ConfigEntry."""
    entry = MagicMock()
    entry.data = {
        "guid": "test-guid",
        "entry_name": "Test",
        "email": email,
        "password": password,
    }
    entry.async_on_unload = MagicMock()
    entry.add_update_listener = MagicMock(return_value=MagicMock())
    return entry


class TestAsyncSetupEntry(unittest.IsolatedAsyncioTestCase):
    """Tests for async_setup_entry in __init__.py."""

    async def test_cannot_connect_raises_config_entry_not_ready(self):
        """When API is unreachable, setup must raise ConfigEntryNotReady immediately."""
        hass = MagicMock()
        entry = _make_mock_entry()

        with (
            patch(
                "homeassistant.components.pajgps._validate_credentials",
                new=AsyncMock(return_value="cannot_connect"),
            ),
            pytest.raises(ConfigEntryNotReady) as ctx,
        ):
            await async_setup_entry(hass, entry)

        assert "PAJ GPS API" in str(ctx.value)

    async def test_invalid_auth_raises_config_entry_not_ready(self):
        """When credentials are wrong, setup must raise ConfigEntryNotReady immediately."""
        hass = MagicMock()
        entry = _make_mock_entry()

        with (
            patch(
                "homeassistant.components.pajgps._validate_credentials",
                new=AsyncMock(return_value="invalid_auth"),
            ),
            pytest.raises(ConfigEntryNotReady) as ctx,
        ):
            await async_setup_entry(hass, entry)

        assert "credentials" in str(ctx.value)

    async def test_coordinator_not_created_on_cannot_connect(self):
        """PajGpsCoordinator must never be instantiated when credentials fail."""
        hass = MagicMock()
        entry = _make_mock_entry()

        with (
            patch(
                "homeassistant.components.pajgps._validate_credentials",
                new=AsyncMock(return_value="cannot_connect"),
            ),
            patch("homeassistant.components.pajgps.PajGpsCoordinator") as MockCoord,
            pytest.raises(ConfigEntryNotReady),
        ):
            await async_setup_entry(hass, entry)

        MockCoord.assert_not_called()

    async def test_coordinator_not_created_on_invalid_auth(self):
        """PajGpsCoordinator must never be instantiated when credentials are invalid."""
        hass = MagicMock()
        entry = _make_mock_entry()

        with (
            patch(
                "homeassistant.components.pajgps._validate_credentials",
                new=AsyncMock(return_value="invalid_auth"),
            ),
            patch("homeassistant.components.pajgps.PajGpsCoordinator") as MockCoord,
            pytest.raises(ConfigEntryNotReady),
        ):
            await async_setup_entry(hass, entry)

        MockCoord.assert_not_called()

    async def test_valid_credentials_completes_setup(self):
        """Valid credentials and a healthy coordinator must return True."""
        hass = MagicMock()
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        entry = _make_mock_entry()

        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()

        with (
            patch(
                "homeassistant.components.pajgps._validate_credentials",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "homeassistant.components.pajgps.PajGpsCoordinator",
                return_value=mock_coordinator,
            ),
        ):
            result = await async_setup_entry(hass, entry)

        assert result

    async def test_valid_credentials_sets_runtime_data(self):
        """The coordinator must be stored in entry.runtime_data on success."""
        hass = MagicMock()
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        entry = _make_mock_entry()

        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()

        with (
            patch(
                "homeassistant.components.pajgps._validate_credentials",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "homeassistant.components.pajgps.PajGpsCoordinator",
                return_value=mock_coordinator,
            ),
        ):
            await async_setup_entry(hass, entry)

        assert entry.runtime_data == mock_coordinator

    async def test_coordinator_first_refresh_failure_raises_config_entry_not_ready(
        self,
    ):
        """If coordinator's first refresh fails, ConfigEntryNotReady must propagate."""
        hass = MagicMock()
        entry = _make_mock_entry()

        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock(
            side_effect=ConfigEntryNotReady("refresh failed")
        )

        with (
            patch(
                "homeassistant.components.pajgps._validate_credentials",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "homeassistant.components.pajgps.PajGpsCoordinator",
                return_value=mock_coordinator,
            ),
            pytest.raises(ConfigEntryNotReady),
        ):
            await async_setup_entry(hass, entry)

    async def test_generic_exception_during_first_refresh_raises_config_entry_not_ready(
        self,
    ):
        """A generic Exception during first refresh must be wrapped in ConfigEntryNotReady (lines 40-41)."""
        hass = MagicMock()
        entry = _make_mock_entry()

        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock(
            side_effect=RuntimeError("unexpected boom")
        )

        with (
            patch(
                "homeassistant.components.pajgps._validate_credentials",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "homeassistant.components.pajgps.PajGpsCoordinator",
                return_value=mock_coordinator,
            ),
            pytest.raises(ConfigEntryNotReady) as ctx,
        ):
            await async_setup_entry(hass, entry)

        assert "Failed to connect" in str(ctx.value)


class TestAsyncRemoveConfigEntryDevice(unittest.IsolatedAsyncioTestCase):
    """Test async_remove_config_entry_device (line 55)."""

    async def test_returns_true(self):
        """Test that async_remove_config_entry_device returns True."""
        result = await async_remove_config_entry_device(
            MagicMock(), MagicMock(), MagicMock()
        )
        assert result


class TestAsyncUpdateListener(unittest.IsolatedAsyncioTestCase):
    """Test _async_update_listener (line 60)."""

    async def test_triggers_reload(self):
        """Test that _async_update_listener triggers a config entry reload."""
        hass = MagicMock()
        hass.config_entries.async_reload = AsyncMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test-entry-id"

        await _async_update_listener(hass, config_entry)

        hass.config_entries.async_reload.assert_awaited_once_with("test-entry-id")


class TestAsyncUnloadEntry(unittest.IsolatedAsyncioTestCase):
    """Test async_unload_entry (lines 67-68)."""

    async def test_unload_shuts_down_coordinator_and_unloads_platforms(self):
        """Test that unloading shuts down the coordinator and unloads platforms."""
        hass = MagicMock()
        hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        mock_coordinator = MagicMock()
        mock_coordinator.async_shutdown = AsyncMock()

        entry = _make_mock_entry()
        entry.runtime_data = mock_coordinator

        result = await async_unload_entry(hass, entry)

        mock_coordinator.async_shutdown.assert_awaited_once()
        assert result
