"""Test for Melissa climate component."""
import unittest
import json
from unittest.mock import Mock

from homeassistant.components.melissa import DATA_MELISSA
from homeassistant.components.sensor import melissa
from homeassistant.components.sensor.melissa import MelissaTemperatureSensor, \
    MelissaHumiditySensor
from homeassistant.const import TEMP_CELSIUS
from tests.common import get_test_home_assistant, load_fixture


class TestMelissa(unittest.TestCase):
    """Tests for Melissa climate."""

    def setUp(self):  # pylint: disable=invalid-name
        """Set up test variables."""
        self.hass = get_test_home_assistant()
        self._serial = '12345678'

        self.api = Mock()
        self.api.fetch_devices.return_value = json.loads(load_fixture(
            'melissa_fetch_devices.json'
        ))
        self.api.status.return_value = json.loads(load_fixture(
            'melissa_status.json'
        ))

        self.api.TEMP = 'temp'
        self.api.HUMIDITY = 'humidity'
        device = self.api.fetch_devices()[self._serial]
        self.temp = MelissaTemperatureSensor(device, self.api)
        self.hum = MelissaHumiditySensor(device, self.api)

    def tearDown(self):  # pylint: disable=invalid-name
        """Teardown this test class. Stop hass."""
        self.hass.stop()

    def test_setup_platform(self):
        """Test setup_platform."""
        self.hass.data[DATA_MELISSA] = self.api

        config = {}
        add_devices = Mock()
        discovery_info = {}

        melissa.setup_platform(self.hass, config, add_devices, discovery_info)

    def test_name(self):
        """Test name property."""
        device = self.api.fetch_devices()[self._serial]
        self.assertEqual(self.temp.name, '{0} {1}'.format(
            device['name'],
            self.temp._type
        ))
        self.assertEqual(self.hum.name, '{0} {1}'.format(
            device['name'],
            self.hum._type
        ))

    def test_state(self):
        """Test state property."""
        device = self.api.status()[self._serial]
        self.temp.update()
        self.assertEqual(self.temp.state, device[self.api.TEMP])
        self.hum.update()
        self.assertEqual(self.hum.state, device[self.api.HUMIDITY])

    def test_unit_of_measurement(self):
        """Test unit of measurement property."""
        self.assertEqual(self.temp.unit_of_measurement, TEMP_CELSIUS)
        self.assertEqual(self.hum.unit_of_measurement, '%')

    def test_update(self):
        """Test for update."""
        self.temp.update()
        self.assertEqual(self.temp.state, 27.4)
        self.hum.update()
        self.assertEqual(self.hum.state, 18.7)

    def test_update_keyerror(self):
        """Test for faulty update."""
        self.temp._api.status.return_value = {}
        self.temp.update()
        self.assertEqual(None, self.temp.state)
        self.hum._api.status.return_value = {}
        self.hum.update()
        self.assertEqual(None, self.hum.state)
