"""
tests.test_shell_command
~~~~~~~~~~~~~~~~~~~~~~~~

Tests demo component.
"""
import os
import tempfile
import unittest

from homeassistant import core
from homeassistant.components import shell_command


class TestShellCommand(unittest.TestCase):
    """ Test the demo module. """

    def setUp(self):  # pylint: disable=invalid-name
        self.hass = core.HomeAssistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """ Stop down stuff we started. """
        self.hass.stop()

    def test_executing_service(self):
        """ Test if able to call a configured service. """
        with tempfile.TemporaryDirectory() as tempdirname:
            path = os.path.join(tempdirname, 'called.txt')
            shell_command.setup(self.hass, {
                'shell_command': {
                    'test_service': "touch {}".format(path)
                }
            })

            self.hass.services.call('shell_command', 'test_service',
                                    blocking=True)

            self.assertTrue(os.path.isfile(path))
