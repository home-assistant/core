"""The tests for the notify file platform."""
import os
import unittest
import tempfile

import homeassistant.components.notify as notify
from homeassistant.components.notify import (
    ATTR_TITLE_DEFAULT)
import homeassistant.util.dt as dt_util

from tests.common import get_test_home_assistant


class TestNotifyFile(unittest.TestCase):
    """Test the file notify."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """"Stop down everything that was started."""
        self.hass.stop()

    def test_bad_config(self):
        """Test set up the platform with bad/missing config."""
        self.assertFalse(notify.setup(self.hass, {
            'notify': {
                'name': 'test',
                'platform': 'file',
            }
        }))

    def test_notify_file(self):
        """Test the notify file output."""
        with tempfile.TemporaryDirectory() as tempdirname:
            filename = os.path.join(tempdirname, 'notify.txt')
            message = 'one, two, testing, testing'
            self.assertTrue(notify.setup(self.hass, {
                'notify': {
                    'name': 'test',
                    'platform': 'file',
                    'filename': filename,
                    'timestamp': 0
                }
            }))
            title = '{} notifications (Log started: {})\n{}\n'.format(
                ATTR_TITLE_DEFAULT,
                dt_util.strip_microseconds(dt_util.utcnow()),
                '-' * 80)

            self.hass.services.call('notify', 'test', {'message': message},
                                    blocking=True)

            result = open(filename).read()
            self.assertEqual(result, "{}{}\n".format(title, message))
