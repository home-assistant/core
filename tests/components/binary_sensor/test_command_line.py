"""
tests.components.binary_sensor.command_line
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests command binary sensor.
"""
import unittest

from homeassistant.const import (STATE_ON, STATE_OFF)
from homeassistant.components.binary_sensor import command_line

from tests.common import get_test_home_assistant


class TestCommandSensorBinarySensor(unittest.TestCase):
    """ Test the Template sensor. """

    def setUp(self):
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """ Stop down stuff we started. """
        self.hass.stop()

    def test_setup(self):
        """ Test sensor setup """
        config = {'name': 'Test',
                  'command': 'echo 1',
                  'payload_on': '1',
                  'payload_off': '0'}
        devices = []

        def add_dev_callback(devs):
            """ callback to add device """
            for dev in devs:
                devices.append(dev)

        command_line.setup_platform(
            self.hass, config, add_dev_callback)

        self.assertEqual(1, len(devices))
        entity = devices[0]
        self.assertEqual('Test', entity.name)
        self.assertEqual(STATE_ON, entity.state)

    def test_setup_bad_config(self):
        """ Test setup with a bad config """
        config = {}

        devices = []

        def add_dev_callback(devs):
            """ callback to add device """
            for dev in devs:
                devices.append(dev)

        self.assertFalse(command_line.setup_platform(
            self.hass, config, add_dev_callback))

        self.assertEqual(0, len(devices))

    def test_template(self):
        """ Test command sensor with template """
        data = command_line.CommandSensorData('echo 10')

        entity = command_line.CommandBinarySensor(
            self.hass, data, 'test', '1.0', '0', '{{ value | multiply(0.1) }}')

        self.assertEqual(STATE_ON, entity.state)

    def test_sensor_off(self):
        """ Test command sensor with template """
        data = command_line.CommandSensorData('echo 0')

        entity = command_line.CommandBinarySensor(
            self.hass, data, 'test', '1', '0', None)

        self.assertEqual(STATE_OFF, entity.state)
