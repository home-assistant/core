"""
Tests for models.py — PajGPSDevice, PajGPSAlert, PajGPSPositionData, PajGPSSensorData.
"""
from __future__ import annotations

import unittest

from homeassistant.components.pajgps.models import (
    PajGPSDevice,
    PajGPSAlert,
    PajGPSPositionData,
    PajGPSSensorData,
)


def _make_device(device_id: int = 1) -> PajGPSDevice:
    """Build a fully populated PajGPSDevice for testing."""
    d = PajGPSDevice(id=device_id)
    d.name = "Test Device"
    d.imei = "123456789"
    d.model = "Test Model"
    d.has_battery = True
    d.has_alarm_sos = True
    d.alarm_sos_enabled = True
    d.has_alarm_shock = True
    d.alarm_shock_enabled = True
    d.has_alarm_voltage = True
    d.alarm_voltage_enabled = True
    d.has_alarm_battery = True
    d.alarm_battery_enabled = True
    d.has_alarm_speed = True
    d.alarm_speed_enabled = True
    d.has_alarm_power_cutoff = True
    d.alarm_power_cutoff_enabled = True
    d.has_alarm_ignition = True
    d.alarm_ignition_enabled = True
    d.has_alarm_drop = True
    d.alarm_drop_enabled = True
    return d


class TestPajGPSDevice(unittest.TestCase):
    """Tests for PajGPSDevice."""

    def test_init_sets_id(self):
        device = PajGPSDevice(id=42)
        self.assertEqual(device.id, 42)

    def test_is_alert_enabled_shock_type_1(self):
        device = _make_device()
        self.assertTrue(device.is_alert_enabled(1))

    def test_is_alert_enabled_battery_type_2(self):
        device = _make_device()
        self.assertTrue(device.is_alert_enabled(2))

    def test_is_alert_enabled_sos_type_4(self):
        device = _make_device()
        self.assertTrue(device.is_alert_enabled(4))

    def test_is_alert_enabled_speed_type_5(self):
        device = _make_device()
        self.assertTrue(device.is_alert_enabled(5))

    def test_is_alert_enabled_power_cutoff_type_6(self):
        device = _make_device()
        self.assertTrue(device.is_alert_enabled(6))

    def test_is_alert_enabled_ignition_type_7(self):
        device = _make_device()
        self.assertTrue(device.is_alert_enabled(7))

    def test_is_alert_enabled_drop_type_9(self):
        device = _make_device()
        self.assertTrue(device.is_alert_enabled(9))

    def test_is_alert_enabled_voltage_type_13(self):
        device = _make_device()
        self.assertTrue(device.is_alert_enabled(13))

    def test_is_alert_enabled_returns_false_when_alert_disabled(self):
        device = _make_device()
        device.alarm_sos_enabled = False
        self.assertFalse(device.is_alert_enabled(4))

    def test_is_alert_enabled_returns_false_when_alert_not_supported(self):
        device = _make_device()
        device.has_alarm_shock = False
        self.assertFalse(device.is_alert_enabled(1))

    def test_is_alert_enabled_returns_false_for_unknown_type(self):
        """Unknown alert type must return False and log an error."""
        device = _make_device()
        result = device.is_alert_enabled(999)
        self.assertFalse(result)

    def test_is_alert_enabled_shock_both_conditions_required(self):
        """Both has_alarm_shock AND alarm_shock_enabled must be True."""
        device = _make_device()
        device.has_alarm_shock = True
        device.alarm_shock_enabled = False
        self.assertFalse(device.is_alert_enabled(1))

        device.has_alarm_shock = False
        device.alarm_shock_enabled = True
        self.assertFalse(device.is_alert_enabled(1))


class TestPajGPSAlert(unittest.TestCase):
    """Tests for PajGPSAlert."""

    def test_init_sets_device_id_and_alert_type(self):
        alert = PajGPSAlert(device_id=5, alert_type=2)
        self.assertEqual(alert.device_id, 5)
        self.assertEqual(alert.alert_type, 2)


class TestPajGPSPositionData(unittest.TestCase):
    """Tests for PajGPSPositionData."""

    def test_init_sets_all_fields(self):
        pos = PajGPSPositionData(
            device_id=1, lat=52.5, lng=13.4, direction=90, speed=50, battery=80
        )
        self.assertEqual(pos.device_id, 1)
        self.assertAlmostEqual(pos.lat, 52.5)
        self.assertAlmostEqual(pos.lng, 13.4)
        self.assertEqual(pos.direction, 90)
        self.assertEqual(pos.speed, 50)
        self.assertEqual(pos.battery, 80)

    def test_elevation_defaults_to_none(self):
        pos = PajGPSPositionData(
            device_id=1, lat=0.0, lng=0.0, direction=0, speed=0, battery=0
        )
        self.assertIsNone(pos.elevation)

    def test_last_elevation_update_defaults_to_zero(self):
        pos = PajGPSPositionData(
            device_id=1, lat=0.0, lng=0.0, direction=0, speed=0, battery=0
        )
        self.assertEqual(pos.last_elevation_update, 0.0)


class TestPajGPSSensorData(unittest.TestCase):
    """Tests for PajGPSSensorData."""

    def test_voltage_defaults_to_zero(self):
        sensor = PajGPSSensorData()
        self.assertEqual(sensor.voltage, 0.0)

    def test_total_update_time_defaults_to_zero(self):
        sensor = PajGPSSensorData()
        self.assertEqual(sensor.total_update_time_ms, 0.0)
