"""
Tests for the three update tiers (devices, positions+sensors, notifications)
and the alert-toggle write path (async_update_alert_state).
"""

from __future__ import annotations

import asyncio
import time
import unittest
from unittest.mock import AsyncMock, MagicMock

from pajgps_api.pajgps_api_error import PajGpsApiError

from homeassistant.components.pajgps.coordinator_data import CoordinatorData

from .test_common import (
    make_coordinator,
    make_device,
    make_trackpoint,
    make_sensor,
    make_notification,
)


class TestDevicesTier(unittest.IsolatedAsyncioTestCase):

    async def test_devices_stored_in_snapshot(self):
        coord = make_coordinator()
        devices = [make_device(1), make_device(2)]
        coord.api.get_devices = AsyncMock(return_value=devices)

        received = []
        coord.async_set_updated_data = lambda d: received.append(d)

        await coord._run_devices_tier()

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].devices, devices)

    async def test_api_error_preserves_stale_data(self):
        coord = make_coordinator()
        coord.data = CoordinatorData(devices=[make_device(1)])
        coord.api.get_devices = AsyncMock(side_effect=PajGpsApiError("fail"))

        received = []
        coord.async_set_updated_data = lambda d: received.append(d)

        await coord._run_devices_tier()

        # async_set_updated_data should NOT have been called
        self.assertEqual(len(received), 0)
        # Existing data unchanged
        self.assertEqual(len(coord.data.devices), 1)

    async def test_timestamp_updated_even_on_error(self):
        coord = make_coordinator()
        coord.api.get_devices = AsyncMock(side_effect=PajGpsApiError("fail"))
        coord.async_set_updated_data = MagicMock()

        before = time.monotonic()
        await coord._run_devices_tier()
        self.assertGreaterEqual(coord._last_devices_fetch, before)


class TestPositionsTier(unittest.IsolatedAsyncioTestCase):

    async def _coord_with_device(self, device_id=1, **entry_kwargs):
        coord = make_coordinator(**entry_kwargs)
        coord.data = CoordinatorData(devices=[make_device(device_id)])
        coord.api.get_all_last_positions = AsyncMock(return_value=[make_trackpoint(device_id)])
        coord.api.get_last_sensor_data = AsyncMock(return_value=make_sensor(device_id))
        return coord

    async def test_positions_pushed_immediately(self):
        coord = await self._coord_with_device(1)

        snapshots = []
        coord.async_set_updated_data = lambda d: snapshots.append(d)

        await coord._run_positions_tier()

        # First snapshot should have positions
        self.assertTrue(any(1 in s.positions for s in snapshots))

    async def test_sensor_data_pushed_per_device(self):
        coord = await self._coord_with_device(1)

        snapshots = []
        coord.async_set_updated_data = lambda d: snapshots.append(d)

        await coord._run_positions_tier()
        await asyncio.sleep(0.3)  # let queue worker flush

        self.assertTrue(any(1 in s.sensor_data for s in snapshots))

    async def test_position_api_error_does_not_push(self):
        coord = make_coordinator()
        coord.data = CoordinatorData(devices=[make_device(1)])
        coord.api.get_all_last_positions = AsyncMock(side_effect=PajGpsApiError("fail"))

        received = []
        coord.async_set_updated_data = lambda d: received.append(d)

        await coord._run_positions_tier()

        self.assertEqual(len(received), 0)

    async def test_no_devices_exits_early(self):
        coord = make_coordinator()
        coord.data = CoordinatorData(devices=[])
        coord.api.get_all_last_positions = AsyncMock()

        await coord._run_positions_tier()

        coord.api.get_all_last_positions.assert_not_awaited()

    async def test_sensor_none_response_is_silently_ignored(self):
        """When sensor API returns None, no snapshot should be pushed (line 206)."""
        coord = make_coordinator()
        coord.data = CoordinatorData(devices=[make_device(1)])
        coord.api.get_all_last_positions = AsyncMock(return_value=[make_trackpoint(1)])
        coord.api.get_last_sensor_data = AsyncMock(return_value=None)

        snapshots = []
        coord.async_set_updated_data = lambda d: snapshots.append(d)

        await coord._run_positions_tier()
        await asyncio.sleep(0.3)

        # No sensor_data snapshot should have device 1 in sensor_data
        self.assertFalse(any(1 in s.sensor_data for s in snapshots))

    async def test_sensor_empty_list_response_is_silently_ignored(self):
        """When sensor API returns [], no snapshot should be pushed (line 206)."""
        coord = make_coordinator()
        coord.data = CoordinatorData(devices=[make_device(1)])
        coord.api.get_all_last_positions = AsyncMock(return_value=[make_trackpoint(1)])
        coord.api.get_last_sensor_data = AsyncMock(return_value=[])

        snapshots = []
        coord.async_set_updated_data = lambda d: snapshots.append(d)

        await coord._run_positions_tier()
        await asyncio.sleep(0.3)

        self.assertFalse(any(1 in s.sensor_data for s in snapshots))

    async def test_unexpected_response_format_exception_logs_debug(self):
        """'Unexpected response format' exception logs at DEBUG, not WARNING (lines 212-219)."""
        coord = make_coordinator()
        coord.data = CoordinatorData(devices=[make_device(1)])
        coord.api.get_all_last_positions = AsyncMock(return_value=[make_trackpoint(1)])
        coord.api.get_last_sensor_data = AsyncMock(
            side_effect=Exception("Unexpected response format: []")
        )

        import logging
        with self.assertLogs("homeassistant.components.pajgps.coordinator", level=logging.DEBUG) as cm:
            await coord._run_positions_tier()
            await asyncio.sleep(0.3)

        debug_messages = [m for m in cm.output if "DEBUG" in m and "lack sensors" in m]
        self.assertTrue(len(debug_messages) > 0)

    async def test_generic_sensor_exception_logs_warning(self):
        """A generic sensor exception must log at WARNING (lines 218-219)."""
        coord = make_coordinator()
        coord.data = CoordinatorData(devices=[make_device(1)])
        coord.api.get_all_last_positions = AsyncMock(return_value=[make_trackpoint(1)])
        coord.api.get_last_sensor_data = AsyncMock(
            side_effect=Exception("Some other network error")
        )

        import logging
        with self.assertLogs("homeassistant.components.pajgps.coordinator", level=logging.WARNING) as cm:
            await coord._run_positions_tier()
            await asyncio.sleep(0.3)

        warning_messages = [m for m in cm.output if "WARNING" in m and "Failed to fetch sensor" in m]
        self.assertTrue(len(warning_messages) > 0)


class TestNotificationsTier(unittest.IsolatedAsyncioTestCase):

    async def test_unread_notifications_pushed_per_device(self):
        coord = make_coordinator()
        coord.data = CoordinatorData(devices=[make_device(1)])

        unread = [make_notification(1, alert_type=2, is_read=0)]
        read = [make_notification(1, alert_type=4, is_read=1)]
        coord.api.get_device_notifications = AsyncMock(return_value=unread + read)

        snapshots = []
        coord.async_set_updated_data = lambda d: snapshots.append(d)

        await coord._run_notifications_tier()
        await asyncio.sleep(0.3)

        notif_snapshots = [s for s in snapshots if 1 in s.notifications]
        self.assertTrue(len(notif_snapshots) > 0)
        # Only the unread one should appear
        self.assertEqual(len(notif_snapshots[-1].notifications[1]), 1)
        self.assertEqual(notif_snapshots[-1].notifications[1][0].meldungtyp, 2)

    async def test_mark_as_read_fired_when_configured(self):
        coord = make_coordinator(mark_alerts_as_read=True)
        coord.data = CoordinatorData(devices=[make_device(1)])

        unread = [make_notification(1, is_read=0)]
        coord.api.get_device_notifications = AsyncMock(return_value=unread)
        coord.api.mark_notifications_read_by_device = AsyncMock()

        tasks = []
        coord.hass.async_create_task = lambda coro: tasks.append(coro) or asyncio.ensure_future(coro)
        coord.async_set_updated_data = MagicMock()

        await coord._run_notifications_tier()
        await asyncio.sleep(0.3)
        # Drain any fire-and-forget tasks
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        coord.api.mark_notifications_read_by_device.assert_awaited_once_with(1, is_read=1)

    async def test_mark_as_read_not_fired_when_not_configured(self):
        coord = make_coordinator(mark_alerts_as_read=False)
        coord.data = CoordinatorData(devices=[make_device(1)])

        coord.api.get_device_notifications = AsyncMock(return_value=[make_notification(1)])
        coord.api.mark_notifications_read_by_device = AsyncMock()

        coord.async_set_updated_data = MagicMock()

        await coord._run_notifications_tier()
        await asyncio.sleep(0.3)

        coord.api.mark_notifications_read_by_device.assert_not_awaited()

    async def test_no_devices_exits_early(self):
        coord = make_coordinator()
        coord.data = CoordinatorData(devices=[])
        coord.api.get_device_notifications = AsyncMock()

        await coord._run_notifications_tier()

        coord.api.get_device_notifications.assert_not_awaited()

    async def test_none_notifications_response_is_silently_ignored(self):
        """When notifications API returns None, no snapshot is pushed (line 308)."""
        coord = make_coordinator()
        coord.data = CoordinatorData(devices=[make_device(1)])
        coord.api.get_device_notifications = AsyncMock(return_value=None)

        snapshots = []
        coord.async_set_updated_data = lambda d: snapshots.append(d)

        await coord._run_notifications_tier()
        await asyncio.sleep(0.3)

        self.assertFalse(any(1 in s.notifications for s in snapshots))

    async def test_notification_exception_logs_warning(self):
        """An exception in _collect_notifications must log a WARNING (line 320)."""
        coord = make_coordinator()
        coord.data = CoordinatorData(devices=[make_device(1)])
        coord.api.get_device_notifications = AsyncMock(
            side_effect=Exception("network blip")
        )

        import logging
        with self.assertLogs("homeassistant.components.pajgps.coordinator", level=logging.WARNING) as cm:
            await coord._run_notifications_tier()
            await asyncio.sleep(0.3)

        warning_messages = [m for m in cm.output if "WARNING" in m and "Failed to fetch notifications" in m]
        self.assertTrue(len(warning_messages) > 0)


class TestAlertToggle(unittest.IsolatedAsyncioTestCase):

    async def test_turn_on_sends_put_immediately(self):
        coord = make_coordinator()
        device = make_device(1, alarmbewegung=0)
        coord.data = CoordinatorData(devices=[device])
        coord.api.update_device = AsyncMock(return_value=make_device(1, alarmbewegung=1))

        received = []
        coord.async_set_updated_data = lambda d: received.append(d)

        await coord.async_update_alert_state(1, alert_type=1, enabled=True)

        coord.api.update_device.assert_awaited_once_with(1, alarmbewegung=1)
        # Optimistic snapshot pushed
        self.assertEqual(len(received), 1)
        updated_device = next(d for d in received[0].devices if d.id == 1)
        self.assertEqual(updated_device.alarmbewegung, 1)

    async def test_turn_off_sends_put_with_zero(self):
        coord = make_coordinator()
        device = make_device(1, alarmsos=1)
        coord.data = CoordinatorData(devices=[device])
        coord.api.update_device = AsyncMock(return_value=make_device(1, alarmsos=0))

        coord.async_set_updated_data = MagicMock()

        await coord.async_update_alert_state(1, alert_type=4, enabled=False)

        coord.api.update_device.assert_awaited_once_with(1, alarmsos=0)

    async def test_api_error_does_not_push_snapshot(self):
        coord = make_coordinator()
        coord.data = CoordinatorData(devices=[make_device(1)])
        coord.api.update_device = AsyncMock(side_effect=PajGpsApiError("fail"))

        received = []
        coord.async_set_updated_data = lambda d: received.append(d)

        await coord.async_update_alert_state(1, alert_type=1, enabled=True)

        self.assertEqual(len(received), 0)

    async def test_unknown_alert_type_does_not_call_api(self):
        coord = make_coordinator()
        coord.data = CoordinatorData(devices=[make_device(1)])
        coord.api.update_device = AsyncMock()

        await coord.async_update_alert_state(1, alert_type=999, enabled=True)

        coord.api.update_device.assert_not_awaited()

    async def test_no_refresh_triggered_after_toggle(self):
        """Coordinator must NOT call async_request_refresh after a toggle."""
        coord = make_coordinator()
        coord.data = CoordinatorData(devices=[make_device(1)])
        coord.api.update_device = AsyncMock(return_value=make_device(1))
        coord.async_request_refresh = AsyncMock()
        coord.async_set_updated_data = MagicMock()

        await coord.async_update_alert_state(1, alert_type=1, enabled=True)

        coord.async_request_refresh.assert_not_awaited()
