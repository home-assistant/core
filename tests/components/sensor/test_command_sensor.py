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

        self.config = {'name': 'Test',
                       'unit_of_measurement': 'in',
                       'command': 'echo 5',
                       'value_template': '{{ value }}'}

    def tearDown(self):
        """ Stop down stuff we started. """
        self.hass.stop()

    def test_setup(self):
        """ Test sensor setup """
        devices = []

        def add_dev_callback(devs):
            """ callback to add device """
            for dev in devs:
                devices.append(dev)

        command_sensor.setup_platform(
            self.hass, self.config, add_dev_callback)

        self.assertEqual(1, len(devices))
        entity = devices[0]
        self.assertEqual('Test', entity.name)
        self.assertEqual('in', entity.unit_of_measurement)
        self.assertEqual('5', entity.state)
