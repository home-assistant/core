"""The tests for the Command line sensor platform."""
import unittest

from homeassistant.helpers.template import Template
from homeassistant.components.sensor import command_line
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

        def add_dev_callback(devs, update):
            """Add callback to add devices."""
            for dev in devs:
                devices.append(dev)

        command_line.setup_platform(self.hass, config, add_dev_callback)

        self.assertEqual(1, len(devices))
        entity = devices[0]
        entity.update()
        self.assertEqual('Test', entity.name)
        self.assertEqual('in', entity.unit_of_measurement)
        self.assertEqual('5', entity.state)

    def test_template(self):
        """Test command sensor with template."""
        data = command_line.CommandSensorData(self.hass, 'echo 50')

        entity = command_line.CommandSensor(
            self.hass, data, 'test', 'in',
            Template('{{ value | multiply(0.1) }}', self.hass))

        entity.update()
        self.assertEqual(5, float(entity.state))

    def test_template_render(self):
        """Ensure command with templates get rendered properly."""
        self.hass.states.set('sensor.test_state', 'Works')
        data = command_line.CommandSensorData(
            self.hass,
            'echo {{ states.sensor.test_state.state }}'
        )
        data.update()

        self.assertEqual("Works", data.value)

    def test_bad_command(self):
        """Test bad command."""
        data = command_line.CommandSensorData(self.hass, 'asdfasdf')
        data.update()

        self.assertEqual(None, data.value)
