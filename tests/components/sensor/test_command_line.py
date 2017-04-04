"""The tests for the Command line sensor platform."""
import unittest

from homeassistant.helpers.template import Template
from homeassistant.components.sensor import command_line
from homeassistant import setup
from tests.common import get_test_home_assistant


class TestCommandSensorSensor(unittest.TestCase):
    """Test the Command line sensor."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup(self):
        """Test sensor setup."""
        config = {'name': 'Test',
                  'unit_of_measurement': 'in',
                  'command': 'echo 5'
                  }
        devices = []

        def add_dev_callback(devs):
            """Add callback to add devices."""
            for dev in devs:
                devices.append(dev)

        command_line.setup_platform(self.hass, config, add_dev_callback)

        self.assertEqual(1, len(devices))
        entity = devices[0]
        self.assertEqual('Test', entity.name)
        self.assertEqual('in', entity.unit_of_measurement)
        self.assertEqual('5', entity.state)

    def test_setup_bad_config(self):
        """Test setup with a bad configuration."""
        config = {'name': 'test',
                  'platform': 'not_command_line',
                  }

        self.assertFalse(setup.setup_component(self.hass, 'test', {
            'command_line': config,
        }))

    def test_template(self):
        """Test command sensor with template."""
        data = command_line.CommandSensorData('echo 50')

        entity = command_line.CommandSensor(
            self.hass, data, 'test', 'in',
            Template('{{ value | multiply(0.1) }}', self.hass))

        self.assertEqual(5, float(entity.state))

    def test_bad_command(self):
        """Test bad command."""
        data = command_line.CommandSensorData('asdfasdf')
        data.update()

        self.assertEqual(None, data.value)
