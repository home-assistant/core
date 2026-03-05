"""
Tests for sensor.py entity property methods:
  - PajGPSVoltageSensor.native_value
  - PajGPSBatterySensor.native_value and icon
  - PajGPSSpeedSensor.native_value
  - PajGPSElevationSensor.native_value
  - async_setup_entry warning when no entities
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from pajgps_api.models.sensordata import SensorData

from homeassistant.components.pajgps.coordinator_data import CoordinatorData
from homeassistant.components.pajgps.sensor import (
    PajGPSVoltageSensor,
    PajGPSBatterySensor,
    PajGPSSpeedSensor,
    PajGPSElevationSensor,
)

from .test_common import make_coordinator, make_device, make_trackpoint


def _make_sensor_entity(cls, device_id=1, positions=None, sensor_data=None, elevations=None):
    coord = make_coordinator()
    coord.data = CoordinatorData(
        devices=[make_device(device_id)],
        positions=positions or {},
        sensor_data=sensor_data or {},
        elevations=elevations or {},
    )
    return cls(coord, device_id)


class TestPajGPSVoltageSensor(unittest.TestCase):
    """Tests for PajGPSVoltageSensor."""

    def test_unique_id_is_set(self):
        entity = _make_sensor_entity(PajGPSVoltageSensor)
        self.assertEqual(entity._attr_unique_id, "pajgps_test-guid_1_voltage")

    def test_native_value_converts_millivolts_to_volts(self):
        sd = SensorData(volt=12000, did=1)
        entity = _make_sensor_entity(PajGPSVoltageSensor, sensor_data={1: sd})
        self.assertAlmostEqual(entity.native_value, 12.0)

    def test_native_value_returns_none_when_no_sensor_data(self):
        entity = _make_sensor_entity(PajGPSVoltageSensor, sensor_data={})
        self.assertIsNone(entity.native_value)

    def test_native_value_returns_none_when_volt_is_none(self):
        sd = SensorData(volt=None, did=1)
        entity = _make_sensor_entity(PajGPSVoltageSensor, sensor_data={1: sd})
        self.assertIsNone(entity.native_value)

    def test_native_value_clamped_to_zero_minimum(self):
        sd = SensorData(volt=-5000, did=1)
        entity = _make_sensor_entity(PajGPSVoltageSensor, sensor_data={1: sd})
        self.assertEqual(entity.native_value, 0.0)

    def test_native_value_clamped_to_300_maximum(self):
        sd = SensorData(volt=999999, did=1)
        entity = _make_sensor_entity(PajGPSVoltageSensor, sensor_data={1: sd})
        self.assertEqual(entity.native_value, 300.0)

    def test_device_info_returned(self):
        entity = _make_sensor_entity(PajGPSVoltageSensor)
        self.assertIsNotNone(entity.device_info)


class TestPajGPSBatterySensor(unittest.TestCase):
    """Tests for PajGPSBatterySensor."""

    def test_unique_id_is_set(self):
        entity = _make_sensor_entity(PajGPSBatterySensor)
        self.assertEqual(entity._attr_unique_id, "pajgps_test-guid_1_battery")

    def test_native_value_returns_battery_percentage(self):
        tp = make_trackpoint(device_id=1, battery=75)
        entity = _make_sensor_entity(PajGPSBatterySensor, positions={1: tp})
        self.assertEqual(entity.native_value, 75)

    def test_native_value_returns_none_when_no_position(self):
        entity = _make_sensor_entity(PajGPSBatterySensor, positions={})
        self.assertIsNone(entity.native_value)

    def test_native_value_returns_none_when_battery_is_none(self):
        tp = make_trackpoint(device_id=1)
        tp.battery = None
        entity = _make_sensor_entity(PajGPSBatterySensor, positions={1: tp})
        self.assertIsNone(entity.native_value)

    def test_native_value_clamped_to_zero_minimum(self):
        tp = make_trackpoint(device_id=1, battery=-5)
        entity = _make_sensor_entity(PajGPSBatterySensor, positions={1: tp})
        self.assertEqual(entity.native_value, 0)

    def test_native_value_clamped_to_100_maximum(self):
        tp = make_trackpoint(device_id=1, battery=150)
        entity = _make_sensor_entity(PajGPSBatterySensor, positions={1: tp})
        self.assertEqual(entity.native_value, 100)

    def test_icon_battery_alert_when_value_none(self):
        entity = _make_sensor_entity(PajGPSBatterySensor, positions={})
        self.assertEqual(entity.icon, "mdi:battery-alert")

    def test_icon_battery_full_at_100(self):
        tp = make_trackpoint(device_id=1, battery=100)
        entity = _make_sensor_entity(PajGPSBatterySensor, positions={1: tp})
        self.assertEqual(entity.icon, "mdi:battery")

    def test_icon_battery_90_at_95(self):
        tp = make_trackpoint(device_id=1, battery=95)
        entity = _make_sensor_entity(PajGPSBatterySensor, positions={1: tp})
        self.assertEqual(entity.icon, "mdi:battery-90")

    def test_icon_battery_80_at_85(self):
        tp = make_trackpoint(device_id=1, battery=85)
        entity = _make_sensor_entity(PajGPSBatterySensor, positions={1: tp})
        self.assertEqual(entity.icon, "mdi:battery-80")

    def test_icon_battery_70_at_75(self):
        tp = make_trackpoint(device_id=1, battery=75)
        entity = _make_sensor_entity(PajGPSBatterySensor, positions={1: tp})
        self.assertEqual(entity.icon, "mdi:battery-70")

    def test_icon_battery_60_at_65(self):
        tp = make_trackpoint(device_id=1, battery=65)
        entity = _make_sensor_entity(PajGPSBatterySensor, positions={1: tp})
        self.assertEqual(entity.icon, "mdi:battery-60")

    def test_icon_battery_50_at_55(self):
        tp = make_trackpoint(device_id=1, battery=55)
        entity = _make_sensor_entity(PajGPSBatterySensor, positions={1: tp})
        self.assertEqual(entity.icon, "mdi:battery-50")

    def test_icon_battery_40_at_45(self):
        tp = make_trackpoint(device_id=1, battery=45)
        entity = _make_sensor_entity(PajGPSBatterySensor, positions={1: tp})
        self.assertEqual(entity.icon, "mdi:battery-40")

    def test_icon_battery_30_at_35(self):
        tp = make_trackpoint(device_id=1, battery=35)
        entity = _make_sensor_entity(PajGPSBatterySensor, positions={1: tp})
        self.assertEqual(entity.icon, "mdi:battery-30")

    def test_icon_battery_20_at_25(self):
        tp = make_trackpoint(device_id=1, battery=25)
        entity = _make_sensor_entity(PajGPSBatterySensor, positions={1: tp})
        self.assertEqual(entity.icon, "mdi:battery-20")

    def test_icon_battery_10_at_15(self):
        tp = make_trackpoint(device_id=1, battery=15)
        entity = _make_sensor_entity(PajGPSBatterySensor, positions={1: tp})
        self.assertEqual(entity.icon, "mdi:battery-10")

    def test_icon_battery_alert_at_5(self):
        tp = make_trackpoint(device_id=1, battery=5)
        entity = _make_sensor_entity(PajGPSBatterySensor, positions={1: tp})
        self.assertEqual(entity.icon, "mdi:battery-alert")

    def test_device_info_returned(self):
        entity = _make_sensor_entity(PajGPSBatterySensor)
        self.assertIsNotNone(entity.device_info)


class TestPajGPSSpeedSensor(unittest.TestCase):
    """Tests for PajGPSSpeedSensor."""

    def test_unique_id_is_set(self):
        entity = _make_sensor_entity(PajGPSSpeedSensor)
        self.assertEqual(entity._attr_unique_id, "pajgps_test-guid_1_speed")

    def test_native_value_returns_speed(self):
        tp = make_trackpoint(device_id=1, speed=60)
        entity = _make_sensor_entity(PajGPSSpeedSensor, positions={1: tp})
        self.assertAlmostEqual(entity.native_value, 60.0)

    def test_native_value_returns_none_when_no_position(self):
        entity = _make_sensor_entity(PajGPSSpeedSensor, positions={})
        self.assertIsNone(entity.native_value)

    def test_native_value_returns_none_when_speed_is_none(self):
        tp = make_trackpoint(device_id=1)
        tp.speed = None
        entity = _make_sensor_entity(PajGPSSpeedSensor, positions={1: tp})
        self.assertIsNone(entity.native_value)

    def test_native_value_clamped_to_zero_minimum(self):
        tp = make_trackpoint(device_id=1, speed=-10)
        entity = _make_sensor_entity(PajGPSSpeedSensor, positions={1: tp})
        self.assertEqual(entity.native_value, 0.0)

    def test_native_value_clamped_to_1000_maximum(self):
        tp = make_trackpoint(device_id=1, speed=9999)
        entity = _make_sensor_entity(PajGPSSpeedSensor, positions={1: tp})
        self.assertEqual(entity.native_value, 1000.0)

    def test_device_info_returned(self):
        entity = _make_sensor_entity(PajGPSSpeedSensor)
        self.assertIsNotNone(entity.device_info)


class TestPajGPSElevationSensor(unittest.TestCase):
    """Tests for PajGPSElevationSensor."""

    def test_unique_id_is_set(self):
        entity = _make_sensor_entity(PajGPSElevationSensor)
        self.assertEqual(entity._attr_unique_id, "pajgps_test-guid_1_elevation")

    def test_native_value_returns_elevation(self):
        entity = _make_sensor_entity(PajGPSElevationSensor, elevations={1: 250})
        self.assertAlmostEqual(entity.native_value, 250.0)

    def test_native_value_returns_none_when_no_elevation(self):
        entity = _make_sensor_entity(PajGPSElevationSensor, elevations={})
        self.assertIsNone(entity.native_value)

    def test_native_value_clamped_to_zero_minimum(self):
        entity = _make_sensor_entity(PajGPSElevationSensor, elevations={1: -100})
        self.assertEqual(entity.native_value, 0.0)

    def test_native_value_clamped_to_10000_maximum(self):
        entity = _make_sensor_entity(PajGPSElevationSensor, elevations={1: 99999})
        self.assertEqual(entity.native_value, 10000.0)

    def test_device_info_returned(self):
        entity = _make_sensor_entity(PajGPSElevationSensor)
        self.assertIsNotNone(entity.device_info)


class TestSensorAsyncSetupEntryNoEntities(unittest.IsolatedAsyncioTestCase):
    """async_setup_entry must log a warning when no sensor entities would be created."""

    async def test_warning_logged_when_no_devices(self):
        from unittest.mock import patch
        from homeassistant.components.pajgps import sensor as sensor_module

        coord = make_coordinator()
        coord.data = CoordinatorData(devices=[])

        config_entry = MagicMock()
        config_entry.runtime_data = coord
        config_entry.data = {"fetch_elevation": False, "force_battery": False}

        added = []
        with patch("homeassistant.components.pajgps.sensor._LOGGER") as mock_log:
            await sensor_module.async_setup_entry(MagicMock(), config_entry, lambda e, **kw: added.extend(e))
            mock_log.warning.assert_called_once()

        self.assertEqual(len(added), 0)

    async def test_warning_logged_when_all_devices_have_none_id(self):
        """Devices with id=None are skipped; warning fires when entities list is empty (line 153)."""
        from unittest.mock import patch
        from homeassistant.components.pajgps import sensor as sensor_module

        no_id_device = make_device(1)
        no_id_device.id = None
        coord = make_coordinator()
        coord.data = CoordinatorData(devices=[no_id_device])

        config_entry = MagicMock()
        config_entry.runtime_data = coord
        config_entry.data = {"fetch_elevation": False, "force_battery": False}

        added = []
        with patch("homeassistant.components.pajgps.sensor._LOGGER") as mock_log:
            await sensor_module.async_setup_entry(MagicMock(), config_entry, lambda e, **kw: added.extend(e))
            mock_log.warning.assert_called_once()

        self.assertEqual(len(added), 0)
