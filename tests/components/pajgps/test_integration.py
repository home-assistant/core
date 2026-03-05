"""
Real API integration tests for PajGpsCoordinator.
Requires PAJGPS_EMAIL and PAJGPS_PASSWORD environment variables to run.
Skip with:  pytest -k "not Integration"
"""

from __future__ import annotations

import asyncio
import os
import unittest
from unittest.mock import MagicMock

from homeassistant.components.pajgps.coordinator import PajGpsCoordinator
from homeassistant.components.pajgps.coordinator_data import CoordinatorData

from .test_common import make_entry_data


class TestCoordinatorIntegration(unittest.IsolatedAsyncioTestCase):
    """
    Integration tests that hit the real PAJ GPS API.
    Skipped automatically when PAJGPS_EMAIL / PAJGPS_PASSWORD are not set.
    """

    def setUp(self):
        email = os.getenv("PAJGPS_EMAIL")
        password = os.getenv("PAJGPS_PASSWORD")
        if not email or not password:
            self.skipTest("PAJGPS_EMAIL / PAJGPS_PASSWORD not set — skipping integration tests")

        self._entry_data = make_entry_data(email=email, password=password)

    def _make_real_coordinator(self) -> PajGpsCoordinator:
        hass = MagicMock()
        hass.async_create_task = lambda coro: asyncio.ensure_future(coro)
        return PajGpsCoordinator(hass, self._entry_data)

    async def test_login_succeeds(self):
        coord = self._make_real_coordinator()
        await coord.api.login()
        # If no exception, login succeeded

    async def test_fetch_devices(self):
        coord = self._make_real_coordinator()
        await coord.api.login()
        await coord._run_devices_tier()

        self.assertGreater(len(coord.data.devices), 0)
        for device in coord.data.devices:
            self.assertIsNotNone(device.id)
            self.assertIsNotNone(device.name)

    async def test_fetch_positions(self):
        coord = self._make_real_coordinator()
        await coord.api.login()
        await coord._run_devices_tier()
        await coord._run_positions_tier()
        await asyncio.sleep(1)  # let queue workers drain

        self.assertGreater(len(coord.data.positions), 0)
        for device_id, tp in coord.data.positions.items():
            self.assertIsNotNone(tp.lat)
            self.assertIsNotNone(tp.lng)
            self.assertGreaterEqual(tp.speed, 0)
            self.assertIn(tp.battery, range(0, 101))

    async def test_fetch_sensor_data(self):
        coord = self._make_real_coordinator()
        await coord.api.login()
        await coord._run_devices_tier()
        await coord._run_positions_tier()
        await asyncio.sleep(1)

        # At least one device should have sensor data
        self.assertGreater(len(coord.data.sensor_data), 0)

    async def test_fetch_notifications(self):
        coord = self._make_real_coordinator()
        await coord.api.login()
        await coord._run_devices_tier()
        await coord._run_notifications_tier()
        await asyncio.sleep(1)

        # Notifications dict should exist for all known devices
        for device in coord.data.devices:
            self.assertIn(device.id, coord.data.notifications)
            self.assertIsInstance(coord.data.notifications[device.id], list)

    async def test_full_initial_refresh(self):
        coord = self._make_real_coordinator()
        result = await coord._async_update_data()

        self.assertIsInstance(result, CoordinatorData)
        self.assertGreater(len(result.devices), 0)
        self.assertTrue(coord._initial_refresh_done)

    async def test_get_device_info_after_refresh(self):
        coord = self._make_real_coordinator()
        await coord._async_update_data()

        device_id = coord.data.devices[0].id
        info = coord.get_device_info(device_id)

        self.assertIsNotNone(info)
        self.assertEqual(info["manufacturer"], "PAJ GPS")

    async def test_elevation_fetch(self):
        coord = self._make_real_coordinator()
        elevation = await coord._fetch_elevation(52.52, 13.41)  # Berlin
        self.assertIsNotNone(elevation)
        self.assertGreaterEqual(elevation, 0)

    async def tearDown(self):
        # Best-effort cleanup
        try:
            coord = self._make_real_coordinator()
            await coord.async_shutdown()
        except Exception:
            pass
