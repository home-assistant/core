"""
tests.components.binary_sensor.command_sensor
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests command binary sensor.
"""

import unittest

import homeassistant.core as ha
from homeassistant.const import (STATE_ON, STATE_OFF)
from homeassistant.components.binary_sensor import command_sensor


class TestCommandSensorBinarySensor(unittest.TestCase):
    """ Test the Template sensor. """

    def setUp(self):
        self.hass = ha.HomeAssistant()

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

        command_sensor.setup_platform(
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

        self.assertFalse(command_sensor.setup_platform(
            self.hass, config, add_dev_callback))

        self.assertEqual(0, len(devices))

    def test_template(self):
        """ Test command sensor with template """
        data = command_sensor.CommandSensorData('echo 10')

        entity = command_sensor.CommandBinarySensor(
            self.hass, data, 'test', '1.0', '0', '{{ value | multiply(0.1) }}')

        self.assertEqual(STATE_ON, entity.state)

    def test_sensor_off(self):
        """ Test command sensor with template """
        data = command_sensor.CommandSensorData('echo 0')

        entity = command_sensor.CommandBinarySensor(
            self.hass, data, 'test', '1', '0', None)

        self.assertEqual(STATE_OFF, entity.state)
