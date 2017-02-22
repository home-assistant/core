"""Tests for MH-Z19 sensor."""
import unittest
from unittest.mock import patch, DEFAULT, Mock

from homeassistant.bootstrap import setup_component
import homeassistant.components.sensor as sensor
import homeassistant.components.sensor.mhz19 as mhz19

from tests.common import get_test_home_assistant, assert_setup_component


class TestMHZ19Sensor(unittest.TestCase):
    """Test the MH-Z19 sensor."""

    hass = None

    def setup_method(self, method):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup_missing_config(self):
        """Test setup with configuration missing required entries."""
        with assert_setup_component(0):
            assert setup_component(self.hass, sensor.DOMAIN, {
                'sensor': {'platform': 'mhz19'}})

    @patch('pmsensor.co2sensor.read_mh_z19', side_effect=OSError('test error'))
    def test_setup_failed_connect(self, mock_co2):
        """Test setup when connection error occurs."""
        self.assertFalse(mhz19.setup_platform(self.hass, {
            'platform': 'mhz19',
            mhz19.CONF_SERIAL_DEVICE: 'test.serial',
            }, None))

    def test_setup_connected(self):
        """Test setup when connection succeeds."""
        with patch.multiple('pmsensor.co2sensor', read_mh_z19=DEFAULT,
                            read_mh_z19_with_temperature=DEFAULT):
            from pmsensor.co2sensor import read_mh_z19_with_temperature
            read_mh_z19_with_temperature.return_value = None
            mock_add = Mock()
            self.assertTrue(mhz19.setup_platform(self.hass, {
                'platform': 'mhz19',
                'monitored_conditions': ['co2', 'temperature'],
                mhz19.CONF_SERIAL_DEVICE: 'test.serial',
                }, mock_add))
        self.assertEqual(1, mock_add.call_count)
