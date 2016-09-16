"""The tests for the notify file platform."""
import os
import unittest
import tempfile
from unittest.mock import patch

from homeassistant.bootstrap import setup_component
import homeassistant.components.notify as notify
from homeassistant.components.notify import (
    ATTR_TITLE_DEFAULT)
import homeassistant.util.dt as dt_util
from homeassistant.bootstrap import _setup_component

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
        self.assertFalse(_setup_component(self.hass, notify.DOMAIN, {
            'notify': {
                'name': 'test',
                'platform': 'file',
            },
        }))

    @patch('homeassistant.util.dt.utcnow')
    def test_notify_file(self, mock_utcnow):
        """Test the notify file output."""
        mock_utcnow.return_value = dt_util.as_utc(dt_util.now())

        with tempfile.TemporaryDirectory() as tempdirname:
            filename = os.path.join(tempdirname, 'notify.txt')
            message = 'one, two, testing, testing'
            self.assertTrue(setup_component(self.hass, notify.DOMAIN, {
                'notify': {
                    'name': 'test',
                    'platform': 'file',
                    'filename': filename,
                    'timestamp': False,
                }
            }))
            title = '{} notifications (Log started: {})\n{}\n'.format(
                ATTR_TITLE_DEFAULT,
                dt_util.utcnow().isoformat(),
                '-' * 80)

            self.hass.services.call('notify', 'test', {'message': message},
                                    blocking=True)

            result = open(filename).read()
            self.assertEqual(result, "{}{}\n".format(title, message))
