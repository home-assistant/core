"""The tests for the hddtemp platform."""
import unittest
from unittest.mock import patch

from homeassistant.setup import setup_component

from tests.common import (get_test_home_assistant, load_fixture)

VALID_CONFIG_MINIMAL = {
    'sensor': {
        'platform': 'hddtemp',
    }
}

VALID_CONFIG_NAME = {
    'sensor': {
        'platform': 'hddtemp',
        'name': 'FooBar',
    }
}

VALID_CONFIG_ONE_DISK = {
    'sensor': {
        'platform': 'hddtemp',
        'disks': [
            '/dev/sdb1',
        ],
    }
}

VALID_CONFIG_MULTIPLE_DISKS = {
    'sensor': {
        'platform': 'hddtemp',
        'host': 'foobar.local',
        'disks': [
            '/dev/sda1',
            '/dev/sdb1',
            '/dev/sdc1',
        ],
    }
}


class TelnetMock():
    """Mock class for the telnetlib.Telnet object."""

    def __init__(self, host, port, timeout=0):
        """Initialize Telnet object."""
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sample_data = bytes(load_fixture('hddtemp.txt'), 'ascii')

    def read_all(self):
        """Return sample values."""
        return self.sample_data


class TestHDDTempSensor(unittest.TestCase):
    """Test the hddtemp sensor."""

    def setUp(self):
        """Set up things to run when tests begin."""
        self.hass = get_test_home_assistant()
        self.config = VALID_CONFIG_ONE_DISK

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    @patch('telnetlib.Telnet', new=TelnetMock)
    def test_hddtemp_min_config(self):
        """Test minimal hddtemp configuration."""
        assert setup_component(self.hass, 'sensor', VALID_CONFIG_MINIMAL)

        state = self.hass.states.get('sensor.hd_temperature_devsda1')

        self.assertEqual(state.state, '29')
        self.assertEqual(state.attributes.get('device'), '/dev/sda1')
        self.assertEqual(state.attributes.get('model'), 'WDC WD30EZRX-12DC0B0')
        self.assertEqual(state.attributes.get('unit_of_measurement'), '°C')
        self.assertEqual(state.attributes.get('friendly_name'),
                         'HD Temperature /dev/sda1')

    @patch('telnetlib.Telnet', new=TelnetMock)
    def test_hddtemp_rename_config(self):
        """Test hddtemp configuration with different name."""
        assert setup_component(self.hass, 'sensor', VALID_CONFIG_NAME)
        assert self.hass.states.get('sensor.foobar_devsda1')

        state = self.hass.states.get('sensor.foobar_devsda1')

        self.assertEqual(state.attributes.get('friendly_name'),
                         'FooBar /dev/sda1')

    @patch('telnetlib.Telnet', new=TelnetMock)
    def test_hddtemp_one_disk(self):
        """Test hddtemp one disk configuration."""
        assert setup_component(self.hass, 'sensor', VALID_CONFIG_ONE_DISK)

        state = self.hass.states.get('sensor.hd_temperature_devsdb1')

        self.assertEqual(state.state, '32')
        self.assertEqual(state.attributes.get('device'), '/dev/sdb1')
        self.assertEqual(state.attributes.get('model'), 'WDC WD15EADS-11P7B2')
        self.assertEqual(state.attributes.get('unit_of_measurement'), '°C')

    @patch('telnetlib.Telnet', new=TelnetMock)
    def test_hddtemp_multiple_disks(self):
        """Test hddtemp multiple disk configuration."""
        assert setup_component(self.hass,
                               'sensor', VALID_CONFIG_MULTIPLE_DISKS)

        state = self.hass.states.get('sensor.hd_temperature_devsda1')

        self.assertEqual(state.state, '29')
        self.assertEqual(state.attributes.get('device'), '/dev/sda1')
        self.assertEqual(state.attributes.get('model'), 'WDC WD30EZRX-12DC0B0')
        self.assertEqual(state.attributes.get('unit_of_measurement'), '°C')

        state = self.hass.states.get('sensor.hd_temperature_devsdb1')

        self.assertEqual(state.state, '32')
        self.assertEqual(state.attributes.get('device'), '/dev/sdb1')
        self.assertEqual(state.attributes.get('model'), 'WDC WD15EADS-11P7B2')
        self.assertEqual(state.attributes.get('unit_of_measurement'), '°C')

        state = self.hass.states.get('sensor.hd_temperature_devsdc1')

        self.assertEqual(state.state, '29')
        self.assertEqual(state.attributes.get('device'), '/dev/sdc1')
        self.assertEqual(state.attributes.get('model'), 'WDC WD20EARX-22MMMB0')
        self.assertEqual(state.attributes.get('unit_of_measurement'), '°C')
