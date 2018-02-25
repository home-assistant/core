"""The tests for the Command line Binary sensor platform."""
import unittest

from homeassistant.const import (STATE_ON, STATE_OFF)
from homeassistant.components.binary_sensor import command_line
from homeassistant.helpers import template

from tests.common import get_test_home_assistant


class TestCommandSensorBinarySensor(unittest.TestCase):
    """Test the Command line Binary sensor."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup(self):
        """Test sensor setup."""
        config = {'name': 'Test',
                  'command': 'echo 1',
                  'payload_on': '1',
                  'payload_off': '0'}

        devices = []

        def add_dev_callback(devs, update):
            """Add callback to add devices."""
            for dev in devs:
                devices.append(dev)

        command_line.setup_platform(self.hass, config, add_dev_callback)

        self.assertEqual(1, len(devices))
        entity = devices[0]
        entity.update()
        self.assertEqual('Test', entity.name)
        self.assertEqual(STATE_ON, entity.state)

    def test_template(self):
        """Test setting the state with a template."""
        data = command_line.CommandSensorData(self.hass, 'echo 10')

        entity = command_line.CommandBinarySensor(
            self.hass, data, 'test', None, '1.0', '0',
            template.Template('{{ value | multiply(0.1) }}', self.hass))
        entity.update()
        self.assertEqual(STATE_ON, entity.state)

    def test_sensor_off(self):
        """Test setting the state with a template."""
        data = command_line.CommandSensorData(self.hass, 'echo 0')

        entity = command_line.CommandBinarySensor(
            self.hass, data, 'test', None, '1', '0', None)
        entity.update()
        self.assertEqual(STATE_OFF, entity.state)
