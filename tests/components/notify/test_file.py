"""The tests for the notify file platform."""
import os
import unittest
from unittest.mock import call, mock_open, patch

from homeassistant.setup import setup_component
import homeassistant.components.notify as notify
from homeassistant.components.notify import (
    ATTR_TITLE_DEFAULT)
import homeassistant.util.dt as dt_util

from tests.common import assert_setup_component, get_test_home_assistant


class TestNotifyFile(unittest.TestCase):
    """Test the file notify."""

    def setUp(self):  # pylint: disable=invalid-name
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop down everything that was started."""
        self.hass.stop()

    def test_bad_config(self):
        """Test set up the platform with bad/missing config."""
        config = {
            notify.DOMAIN: {
                'name': 'test',
                'platform': 'file',
            },
        }
        with assert_setup_component(0) as handle_config:
            assert setup_component(self.hass, notify.DOMAIN, config)
        assert not handle_config[notify.DOMAIN]

    def _test_notify_file(self, timestamp):
        """Test the notify file output."""
        filename = 'mock_file'
        message = 'one, two, testing, testing'
        with assert_setup_component(1) as handle_config:
            assert setup_component(self.hass, notify.DOMAIN, {
                'notify': {
                    'name': 'test',
                    'platform': 'file',
                    'filename': filename,
                    'timestamp': timestamp,
                }
            })
        assert handle_config[notify.DOMAIN]

        m_open = mock_open()
        with patch(
            'homeassistant.components.notify.file.open',
            m_open, create=True
        ), patch('homeassistant.components.notify.file.os.stat') as mock_st, \
            patch('homeassistant.util.dt.utcnow',
                  return_value=dt_util.utcnow()):

            mock_st.return_value.st_size = 0
            title = '{} notifications (Log started: {})\n{}\n'.format(
                ATTR_TITLE_DEFAULT,
                dt_util.utcnow().isoformat(),
                '-' * 80)

            self.hass.services.call('notify', 'test', {'message': message},
                                    blocking=True)

            full_filename = os.path.join(self.hass.config.path(), filename)
            assert m_open.call_count == 1
            assert m_open.call_args == call(full_filename, 'a')

            assert m_open.return_value.write.call_count == 2
            if not timestamp:
                assert m_open.return_value.write.call_args_list == \
                    [call(title), call('{}\n'.format(message))]
            else:
                assert m_open.return_value.write.call_args_list == \
                    [call(title), call('{} {}\n'.format(
                        dt_util.utcnow().isoformat(), message))]

    def test_notify_file(self):
        """Test the notify file output without timestamp."""
        self._test_notify_file(False)

    def test_notify_file_timestamp(self):
        """Test the notify file output with timestamp."""
        self._test_notify_file(True)
