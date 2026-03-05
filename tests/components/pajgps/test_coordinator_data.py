"""
Tests for CoordinatorData snapshot helpers and apply_alert_flag utility.
"""

from __future__ import annotations

import dataclasses
import unittest

from homeassistant.components.pajgps.coordinator_data import CoordinatorData
from homeassistant.components.pajgps.coordinator_utils import apply_alert_flag
from homeassistant.components.pajgps.const import ALERT_TYPE_TO_DEVICE_FIELD

from .test_common import make_device, make_trackpoint


class TestCoordinatorData(unittest.TestCase):

    def test_default_snapshot_is_empty(self):
        data = CoordinatorData()
        self.assertEqual(data.devices, [])
        self.assertEqual(data.positions, {})
        self.assertEqual(data.sensor_data, {})
        self.assertEqual(data.elevations, {})
        self.assertEqual(data.notifications, {})

    def test_replace_preserves_other_fields(self):
        device = make_device(1)
        data = CoordinatorData(devices=[device])
        tp = make_trackpoint(1)
        new_data = dataclasses.replace(data, positions={1: tp})

        self.assertEqual(new_data.devices, [device])
        self.assertEqual(new_data.positions, {1: tp})
        # Original is untouched (frozen)
        self.assertEqual(data.positions, {})

    def test_snapshot_is_immutable_via_replace(self):
        """Mutating via dataclasses.replace() creates a new object; original is unchanged."""
        device = make_device(1)
        original = CoordinatorData(devices=[device])
        updated = dataclasses.replace(original, positions={1: make_trackpoint(1)})
        # replace() returns a distinct object
        self.assertIsNot(original, updated)
        # original is untouched
        self.assertEqual(original.positions, {})
        # updated carries the new value
        self.assertIn(1, updated.positions)


class TestApplyAlertFlag(unittest.TestCase):

    def test_enables_known_alert(self):
        device = make_device(1, alarmbewegung=0)
        updated = apply_alert_flag(device, alert_type=1, enabled=True)
        self.assertEqual(updated.alarmbewegung, 1)
        # Original unchanged
        self.assertEqual(device.alarmbewegung, 0)

    def test_disables_known_alert(self):
        device = make_device(1, alarmsos=1)
        updated = apply_alert_flag(device, alert_type=4, enabled=False)
        self.assertEqual(updated.alarmsos, 0)

    def test_unknown_alert_type_returns_original(self):
        device = make_device(1)
        result = apply_alert_flag(device, alert_type=999, enabled=True)
        self.assertIs(result, device)

    def test_all_alert_types_round_trip(self):
        for alert_type, field in ALERT_TYPE_TO_DEVICE_FIELD.items():
            device = make_device(1, **{field: 0})
            enabled = apply_alert_flag(device, alert_type, True)
            self.assertEqual(getattr(enabled, field), 1, f"alert_type={alert_type}")
            disabled = apply_alert_flag(enabled, alert_type, False)
            self.assertEqual(getattr(disabled, field), 0, f"alert_type={alert_type}")
