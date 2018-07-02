"""The tests for the Netgear Arlo sensors."""
import asyncio
from collections import namedtuple
import unittest
from unittest import mock
from unittest.mock import patch, MagicMock
from homeassistant.const import (
    DEVICE_CLASS_TEMPERATURE, DEVICE_CLASS_HUMIDITY, ATTR_ATTRIBUTION)
from homeassistant.components.sensor import arlo
from homeassistant.components.arlo import DATA_ARLO
from homeassistant.helpers import dispatcher
from tests.common import get_test_home_assistant


class TestArloSensor(unittest.TestCase):
    """Test Netgear Arlo sensors."""

    def _setup_arlo(self):
        self.hass.data = {
            DATA_ARLO: 'test'
        }

    @staticmethod
    def _get_mock_sensor(name='Last', sensor_type='last_capture', data=None):
        if data is None:
            data = {}
        return arlo.ArloSensor(name, data, sensor_type)

    @staticmethod
    def _get_named_tuple(input_dict):
        return namedtuple('Struct', input_dict.keys())(*input_dict.values())

    def setUp(self):  # pylint: disable=invalid-name
        """Setup shared dependencies for each test."""
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """Tear down shared dependencies for each test."""
        self.hass.stop()

    def test_setup_with_no_data(self):
        """Test setup_platform with no data."""
        result = arlo.setup_platform(self.hass, None, None)
        self.assertEqual(result, False)

    def test_setup_with_valid_data(self):
        """Test setup_platform with valid data."""
        add_devices = mock.MagicMock()
        config = {
            'monitored_conditions': [
                'last_capture',
                'total_cameras',
                'captured_today',
                'battery_level',
                'signal_strength',
                'temperature',
                'humidity',
                'air_quality'
            ]
        }
        self.hass.data[DATA_ARLO] = MagicMock()
        arlo.setup_platform(self.hass, config, add_devices)
        add_devices.assert_called_once()

    def test_sensor_name(self):
        """Test the name property."""
        sensor = TestArloSensor._get_mock_sensor()
        self.assertEqual(sensor.name, 'Last')

    @asyncio.coroutine
    @patch('homeassistant.helpers.dispatcher.async_dispatcher_connect',
           MagicMock())
    async def test_async_added_to_hass(self):
        """Test dispatcher called when added."""
        sensor = TestArloSensor._get_mock_sensor()
        await sensor.async_added_to_hass()
        dispatcher.async_dispatcher_connect.assert_called_once()

    def test_sensor_state_default(self):
        """Test the state property."""
        sensor = TestArloSensor._get_mock_sensor()
        self.assertIsNone(sensor.state)

    def test_sensor_icon_battery(self):
        """Test the battery icon."""
        data = TestArloSensor._get_named_tuple({
            'battery_level': 50
        })

        sensor = TestArloSensor._get_mock_sensor(
            'Battery Level',
            'battery_level',
            data)
        self.assertEqual(sensor.icon, 'mdi:battery-50')

    def test_sensor_icon(self):
        """Test the icon property."""
        sensor = TestArloSensor._get_mock_sensor('Temperature', 'temperature')
        self.assertEqual(sensor.icon, 'mdi:thermometer')

    def test_unit_of_measure(self):
        """Test the unit_of_measurement property."""
        sensor = TestArloSensor._get_mock_sensor()
        self.assertIsNone(sensor.unit_of_measurement)
        sensor = TestArloSensor._get_mock_sensor(
            'Battery Level',
            'battery_level')
        self.assertEqual(sensor.unit_of_measurement, '%')

    def test_device_class(self):
        """Test the device_class property."""
        sensor = TestArloSensor._get_mock_sensor()
        self.assertIsNone(sensor.device_class)
        sensor = TestArloSensor._get_mock_sensor('Temperature', 'temperature')
        self.assertEqual(sensor.device_class, DEVICE_CLASS_TEMPERATURE)
        sensor = TestArloSensor._get_mock_sensor('Humidity', 'humidity')
        self.assertEqual(sensor.device_class, DEVICE_CLASS_HUMIDITY)

    def test_update_total_cameras(self):
        """Test update method for total_cameras sensor type."""
        data = TestArloSensor._get_named_tuple({
            'cameras': [0, 0]
        })
        sensor = TestArloSensor._get_mock_sensor(
            'Arlo Cameras',
            'total_cameras',
            data)
        sensor.update()
        self.assertEqual(sensor.state, 2)

    def test_update_caputred_today(self):
        """Test update method for captured_today sensor type."""
        data = TestArloSensor._get_named_tuple({
            'captured_today': [0, 0, 0, 0, 0]
        })
        sensor = TestArloSensor._get_mock_sensor(
            'Captured Today',
            'captured_today',
            data)
        sensor.update()
        self.assertEqual(sensor.state, 5)

    def _test_update(self, sensor_type, key, value):
        data = TestArloSensor._get_named_tuple({
            key: value
        })
        sensor = TestArloSensor._get_mock_sensor('test', sensor_type, data)
        sensor.update()
        self.assertEqual(sensor.state, value)

    def test_update(self):
        """Test update method for direct transcription sensor types."""
        self._test_update('battery_level', 'battery_level', 100)
        self._test_update('signal_strength', 'signal_strength', 100)
        self._test_update('temperature', 'ambient_temperature', 21.4)
        self._test_update('humidity', 'ambient_humidity', 45.1)
        self._test_update('air_quality', 'ambient_air_quality', 14.2)

    def test_attributes_known_sensor(self):
        """Test attributes for known sensor type."""
        data = TestArloSensor._get_named_tuple({
            'model_id': 'ABC1000'
        })
        sensor = TestArloSensor._get_mock_sensor('test', 'humidity', data)
        attrs = sensor.device_state_attributes
        self.assertEqual(
            attrs.get(ATTR_ATTRIBUTION),
            'Data provided by arlo.netgear.com')
        self.assertEqual(attrs.get('brand'), 'Netgear Arlo')
        self.assertEqual(attrs.get('model'), 'ABC1000')
