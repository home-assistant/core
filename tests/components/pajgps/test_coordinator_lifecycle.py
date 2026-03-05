"""
Tests for PajGpsCoordinator lifecycle: initialisation, tier scheduling,
initial refresh flow, get_device_info helper, and shutdown.
"""

from __future__ import annotations

import asyncio
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from pajgps_api.pajgps_api_error import AuthenticationError

from homeassistant.components.pajgps.coordinator import PajGpsCoordinator
from homeassistant.components.pajgps.coordinator_data import CoordinatorData

from .test_common import make_coordinator, make_device, make_entry_data


class TestCoordinatorInit(unittest.TestCase):

    def test_initial_snapshot_is_empty(self):
        coord = make_coordinator()
        self.assertIsInstance(coord.data, CoordinatorData)
        self.assertEqual(coord.data.devices, [])

    def test_tier_timestamps_start_at_zero(self):
        coord = make_coordinator()
        self.assertEqual(coord._last_devices_fetch, 0.0)
        self.assertEqual(coord._last_positions_fetch, 0.0)
        self.assertEqual(coord._last_notifications_fetch, 0.0)

    def test_initial_refresh_done_is_false(self):
        coord = make_coordinator()
        self.assertFalse(coord._initial_refresh_done)


class TestTierScheduling(unittest.IsolatedAsyncioTestCase):

    async def _make_ready_coordinator(self, **entry_kwargs) -> PajGpsCoordinator:
        """Return a coordinator whose initial refresh is already done."""
        coord = make_coordinator(**entry_kwargs)
        coord._initial_refresh_done = True
        coord.data = CoordinatorData(devices=[make_device(1)])
        return coord

    async def test_devices_tier_triggered_when_overdue(self):
        coord = await self._make_ready_coordinator()
        coord._last_devices_fetch = 0.0  # very overdue

        with patch.object(coord, '_run_devices_tier', new_callable=AsyncMock) as mock_tier:
            coord.hass.async_create_task = lambda coro: asyncio.ensure_future(coro)
            await coord._async_update_data()
            await asyncio.sleep(0.05)
            mock_tier.assert_awaited_once()

    async def test_devices_tier_not_triggered_when_fresh(self):
        coord = await self._make_ready_coordinator()
        coord._last_devices_fetch = time.monotonic()  # just fetched

        with patch.object(coord, '_run_devices_tier', new_callable=AsyncMock) as mock_tier:
            coord.hass.async_create_task = lambda coro: asyncio.ensure_future(coro)
            await coord._async_update_data()
            await asyncio.sleep(0.05)
            mock_tier.assert_not_awaited()

    async def test_notifications_tier_triggered_when_overdue(self):
        coord = await self._make_ready_coordinator()
        coord._last_notifications_fetch = 0.0

        with patch.object(coord, '_run_notifications_tier', new_callable=AsyncMock) as mock_tier:
            coord.hass.async_create_task = lambda coro: asyncio.ensure_future(coro)
            await coord._async_update_data()
            await asyncio.sleep(0.05)
            mock_tier.assert_awaited_once()

    async def test_returns_current_snapshot_on_subsequent_calls(self):
        coord = await self._make_ready_coordinator()
        coord._last_devices_fetch = time.monotonic()
        coord._last_positions_fetch = time.monotonic()
        coord._last_notifications_fetch = time.monotonic()

        result = await coord._async_update_data()
        self.assertIs(result, coord.data)

    async def test_login_failure_raises_update_failed(self):
        from homeassistant.helpers.update_coordinator import UpdateFailed
        coord = make_coordinator()
        coord.api.login = AsyncMock(side_effect=AuthenticationError("bad creds"))

        with self.assertRaises(UpdateFailed):
            await coord._async_update_data()

    async def test_generic_login_exception_raises_update_failed(self):
        """A non-auth exception during login must also raise UpdateFailed (line 125-126)."""
        from homeassistant.helpers.update_coordinator import UpdateFailed
        coord = make_coordinator()
        coord.api.login = AsyncMock(side_effect=ConnectionError("network gone"))

        with self.assertRaises(UpdateFailed) as ctx:
            await coord._async_update_data()

        self.assertIn("connection error", str(ctx.exception).lower())


class TestInitialRefresh(unittest.IsolatedAsyncioTestCase):

    async def test_initial_refresh_runs_all_three_tiers(self):
        coord = make_coordinator()

        with (
            patch.object(coord, '_run_devices_tier', new_callable=AsyncMock) as d,
            patch.object(coord, '_run_positions_tier', new_callable=AsyncMock) as p,
            patch.object(coord, '_run_notifications_tier', new_callable=AsyncMock) as n,
        ):
            await coord._async_update_data()
            d.assert_awaited_once()
            p.assert_awaited_once()
            n.assert_awaited_once()

    async def test_initial_refresh_sets_flag(self):
        coord = make_coordinator()

        with (
            patch.object(coord, '_run_devices_tier', new_callable=AsyncMock),
            patch.object(coord, '_run_positions_tier', new_callable=AsyncMock),
            patch.object(coord, '_run_notifications_tier', new_callable=AsyncMock),
        ):
            await coord._async_update_data()
            self.assertTrue(coord._initial_refresh_done)

    async def test_initial_refresh_returns_data(self):
        coord = make_coordinator()
        coord.data = CoordinatorData(devices=[make_device(1)])

        with (
            patch.object(coord, '_run_devices_tier', new_callable=AsyncMock),
            patch.object(coord, '_run_positions_tier', new_callable=AsyncMock),
            patch.object(coord, '_run_notifications_tier', new_callable=AsyncMock),
        ):
            result = await coord._async_update_data()
            self.assertIsInstance(result, CoordinatorData)


class TestGetDeviceInfo(unittest.TestCase):

    def test_returns_dict_for_known_device(self):
        coord = make_coordinator()
        coord.data = CoordinatorData(devices=[make_device(1)])

        info = coord.get_device_info(1)

        self.assertIsNotNone(info)
        self.assertIn("identifiers", info)
        self.assertIn("name", info)
        self.assertEqual(info["manufacturer"], "PAJ GPS")
        self.assertIn("model", info)
        self.assertIn("sw_version", info)

    def test_returns_none_for_unknown_device(self):
        coord = make_coordinator()
        coord.data = CoordinatorData(devices=[])

        self.assertIsNone(coord.get_device_info(999))

    def test_identifiers_contain_guid_and_device_id(self):
        coord = make_coordinator(guid="my-guid")
        coord.data = CoordinatorData(devices=[make_device(42)])

        info = coord.get_device_info(42)
        identifiers = info["identifiers"]
        self.assertTrue(any("my-guid" in str(i) and "42" in str(i) for i in identifiers))


class TestShutdown(unittest.IsolatedAsyncioTestCase):

    async def test_shutdown_closes_api(self):
        coord = make_coordinator()
        coord.api.close = AsyncMock()

        await coord.async_shutdown()

        coord.api.close.assert_awaited_once()

    async def test_shutdown_cancels_elevation_tasks(self):
        coord = make_coordinator()
        coord.api.close = AsyncMock()

        async def long_running():
            await asyncio.sleep(100)

        task = asyncio.ensure_future(long_running())
        coord._elevation_tasks.add(task)

        await coord.async_shutdown()

        self.assertTrue(task.cancelled())

    async def test_shutdown_empties_elevation_tasks(self):
        coord = make_coordinator()
        coord.api.close = AsyncMock()

        await coord.async_shutdown()

        self.assertEqual(len(coord._elevation_tasks), 0)
