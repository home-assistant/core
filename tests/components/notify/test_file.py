"""The tests for the notify file platform."""
import os
import unittest
from unittest.mock import call, mock_open, patch

from homeassistant.bootstrap import setup_component
import homeassistant.components.notify as notify
from homeassistant.components.notify import (
    ATTR_TITLE_DEFAULT)
import homeassistant.util.dt as dt_util

from tests.common import get_test_home_assistant, assert_setup_component


class TestNotifyFile(unittest.TestCase):
    """Test the file notify."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """"Stop down everything that was started."""
        self.hass.stop()

    @patch('homeassistant.components.notify.file.os.stat')
    @patch('homeassistant.util.dt.utcnow')
    def test_notify_file(self, mock_utcnow, mock_stat):
        """Test the notify file output."""
        mock_utcnow.return_value = dt_util.as_utc(dt_util.now())
        mock_stat.return_value.st_size = 0

        m_open = mock_open()
        with patch(
            'homeassistant.components.notify.file.open',
            m_open, create=True
        ):
            filename = 'mock_file'
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

            full_filename = os.path.join(self.hass.config.path(), filename)
            self.assertEqual(m_open.call_count, 1)
            self.assertEqual(m_open.call_args, call(full_filename, 'a'))

            self.assertEqual(m_open.return_value.write.call_count, 2)
            self.assertEqual(
                m_open.return_value.write.call_args_list,
                [call(title), call(message + '\n')]
            )
