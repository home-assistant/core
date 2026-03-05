"""
Tests for device_tracker.py — PajGPSPositionSensor and async_setup_entry.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from homeassistant.components.pajgps.coordinator_data import CoordinatorData
from homeassistant.components.pajgps.device_tracker import PajGPSPositionSensor

from .test_common import make_coordinator, make_device, make_trackpoint


def _make_hass_and_config_entry(coordinator):
    config_entry = MagicMock()
    config_entry.entry_id = "test_entry_id"
    config_entry.runtime_data = coordinator
    hass = MagicMock()
    return hass, config_entry


class TestPajGPSPositionSensor(unittest.TestCase):
    """Tests for PajGPSPositionSensor properties."""

    def _make_sensor(self, device_id: int = 1, positions=None, elevations=None):
        coord = make_coordinator()
        coord.data = CoordinatorData(
            devices=[make_device(device_id)],
            positions=positions or {},
            elevations=elevations or {},
        )
        return PajGPSPositionSensor(coord, device_id)

    def test_unique_id_is_set(self):
        sensor = self._make_sensor(1)
        self.assertEqual(sensor._attr_unique_id, "pajgps_test-guid_1_gps")

    def test_latitude_returns_float_when_position_exists(self):
        tp = make_trackpoint(device_id=1, lat=52.5, lng=13.4)
        sensor = self._make_sensor(1, positions={1: tp})
        self.assertAlmostEqual(sensor.latitude, 52.5)

    def test_latitude_returns_none_when_no_position(self):
        sensor = self._make_sensor(1, positions={})
        self.assertIsNone(sensor.latitude)

    def test_latitude_returns_none_when_lat_is_none(self):
        tp = make_trackpoint(device_id=1, lat=None, lng=13.4)
        sensor = self._make_sensor(1, positions={1: tp})
        self.assertIsNone(sensor.latitude)

    def test_longitude_returns_float_when_position_exists(self):
        tp = make_trackpoint(device_id=1, lat=52.5, lng=13.4)
        sensor = self._make_sensor(1, positions={1: tp})
        self.assertAlmostEqual(sensor.longitude, 13.4)

    def test_longitude_returns_none_when_no_position(self):
        sensor = self._make_sensor(1, positions={})
        self.assertIsNone(sensor.longitude)

    def test_longitude_returns_none_when_lng_is_none(self):
        tp = make_trackpoint(device_id=1, lat=52.5, lng=None)
        sensor = self._make_sensor(1, positions={1: tp})
        self.assertIsNone(sensor.longitude)

    def test_source_type_is_gps(self):
        sensor = self._make_sensor(1)
        self.assertEqual(sensor.source_type, "gps")

    def test_extra_state_attributes_includes_elevation_when_present(self):
        sensor = self._make_sensor(1, elevations={1: 150})
        attrs = sensor.extra_state_attributes
        self.assertEqual(attrs["elevation"], 150)

    def test_extra_state_attributes_empty_when_no_elevation(self):
        sensor = self._make_sensor(1, elevations={})
        self.assertEqual(sensor.extra_state_attributes, {})

    def test_device_info_returned_from_coordinator(self):
        sensor = self._make_sensor(1)
        info = sensor.device_info
        self.assertIsNotNone(info)
        self.assertIn("identifiers", info)


class TestDeviceTrackerAsyncSetupEntry(unittest.IsolatedAsyncioTestCase):
    """Tests for async_setup_entry in device_tracker.py."""

    async def test_entities_added_for_each_device(self):
        from homeassistant.components.pajgps import device_tracker as dt_module

        coord = make_coordinator()
        coord.data = CoordinatorData(devices=[make_device(1), make_device(2)])
        hass, config_entry = _make_hass_and_config_entry(coord)

        added = []
        await dt_module.async_setup_entry(hass, config_entry, lambda e, **kw: added.extend(e))

        self.assertEqual(len(added), 2)
        self.assertIsInstance(added[0], PajGPSPositionSensor)

    async def test_no_entities_added_and_warning_logged_when_no_devices(self):
        from unittest.mock import patch
        from homeassistant.components.pajgps import device_tracker as dt_module

        coord = make_coordinator()
        coord.data = CoordinatorData(devices=[])
        hass, config_entry = _make_hass_and_config_entry(coord)

        added = []
        with patch("homeassistant.components.pajgps.device_tracker._LOGGER") as mock_log:
            await dt_module.async_setup_entry(hass, config_entry, lambda e, **kw: added.extend(e))
            mock_log.warning.assert_called_once()

        self.assertEqual(len(added), 0)

    async def test_devices_with_none_id_are_skipped(self):
        from homeassistant.components.pajgps import device_tracker as dt_module

        no_id_device = make_device(1)
        no_id_device.id = None
        coord = make_coordinator()
        coord.data = CoordinatorData(devices=[no_id_device])
        hass, config_entry = _make_hass_and_config_entry(coord)

        added = []
        with unittest.mock.patch("homeassistant.components.pajgps.device_tracker._LOGGER"):
            await dt_module.async_setup_entry(hass, config_entry, lambda e, **kw: added.extend(e))

        self.assertEqual(len(added), 0)
