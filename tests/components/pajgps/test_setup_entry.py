"""Unit tests for __init__.py async_setup_entry.

Coverage:
- coordinator success → returns True, runtime_data set
- coordinator first-refresh fails (ConfigEntryNotReady) → propagates
- coordinator first-refresh fails (generic exception) → propagates unchanged
"""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.pajgps import (
    _async_update_listener,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.components.pajgps.const import DOMAIN
from homeassistant.components.pajgps.coordinator import PajGpsData
from homeassistant.exceptions import ConfigEntryNotReady


def _make_mock_entry(
    email: str = "user@example.com", password: str = "secret"
) -> MagicMock:
    """Return a minimal mock ConfigEntry."""
    entry = MagicMock()
    entry.data = {
        "guid": "test-guid",
        "email": email,
        "password": password,
    }
    entry.async_on_unload = MagicMock()
    entry.add_update_listener = MagicMock(return_value=MagicMock())
    return entry


class TestAsyncSetupEntry(unittest.IsolatedAsyncioTestCase):
    """Tests for async_setup_entry in __init__.py."""

    async def test_valid_credentials_completes_setup(self):
        """A healthy coordinator must cause setup to return True."""
        hass = MagicMock()
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        entry = _make_mock_entry()

        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()

        with (
            patch(
                "homeassistant.components.pajgps.async_get_clientsession",
                return_value=MagicMock(),
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
                "homeassistant.components.pajgps.async_get_clientsession",
                return_value=MagicMock(),
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
                "homeassistant.components.pajgps.async_get_clientsession",
                return_value=MagicMock(),
            ),
            patch(
                "homeassistant.components.pajgps.PajGpsCoordinator",
                return_value=mock_coordinator,
            ),
            pytest.raises(ConfigEntryNotReady),
        ):
            await async_setup_entry(hass, entry)

    async def test_generic_exception_during_first_refresh_propagates(
        self,
    ):
        """A generic Exception during first refresh propagates unchanged."""
        hass = MagicMock()
        entry = _make_mock_entry()

        mock_coordinator = MagicMock()
        mock_coordinator.async_config_entry_first_refresh = AsyncMock(
            side_effect=RuntimeError("unexpected boom")
        )

        with (
            patch(
                "homeassistant.components.pajgps.async_get_clientsession",
                return_value=MagicMock(),
            ),
            patch(
                "homeassistant.components.pajgps.PajGpsCoordinator",
                return_value=mock_coordinator,
            ),
            pytest.raises(RuntimeError) as ctx,
        ):
            await async_setup_entry(hass, entry)

        assert "unexpected boom" in str(ctx.value)


class TestAsyncRemoveConfigEntryDevice(unittest.IsolatedAsyncioTestCase):
    """Test async_remove_config_entry_device."""

    def _make_entry_and_coordinator(self, live_device_ids: list[int]):
        """Build a mock config entry and coordinator with the given live device IDs."""
        entry = _make_mock_entry()
        coordinator = MagicMock()
        devices = []
        for dev_id in live_device_ids:
            dev = MagicMock()
            dev.id = dev_id
            devices.append(dev)
        coordinator.data = PajGpsData(devices=devices)
        entry.runtime_data = coordinator
        return entry

    def _make_device_entry(self, identifier: str):
        """Build a mock DeviceEntry whose only identifier is (DOMAIN, identifier)."""
        device_entry = MagicMock()
        device_entry.identifiers = {(DOMAIN, identifier)}
        return device_entry


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
