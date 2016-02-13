"""
tests.components.sensor.command_sensor
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests command sensor.
"""

import unittest

import homeassistant.core as ha
from homeassistant.components.sensor import command_sensor


class TestCommandSensorSensor(unittest.TestCase):
    """ Test the Template sensor. """

    def setUp(self):
        self.hass = ha.HomeAssistant()

    def tearDown(self):
        """ Stop down stuff we started. """
        self.hass.stop()

    def test_setup(self):
        """ Test sensor setup """
        config = {'name': 'Test',
                  'unit_of_measurement': 'in',
                  'command': 'echo 5'}
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
        self.assertEqual('in', entity.unit_of_measurement)
        self.assertEqual('5', entity.state)

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
        data = command_sensor.CommandSensorData('echo 50')

        entity = command_sensor.CommandSensor(
            self.hass, data, 'test', 'in', '{{ value | multiply(0.1) }}')

        self.assertEqual(5, float(entity.state))

    def test_bad_command(self):
        """ Test bad command """
        data = command_sensor.CommandSensorData('asdfasdf')
        data.update()

        self.assertEqual(None, data.value)
