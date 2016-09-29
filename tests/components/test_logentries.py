"""The tests for the Logentries component."""

import unittest
from unittest import mock

from homeassistant.bootstrap import setup_component
import homeassistant.components.logentries as logentries
from homeassistant.const import STATE_ON, STATE_OFF, EVENT_STATE_CHANGED


class TestLogentries(unittest.TestCase):
    """Test the Logentries component."""

    def test_setup_config_full(self):
        """Test setup with all data."""
        config = {
            'logentries': {
                'token': 'secret',
            }
        }
        hass = mock.MagicMock()
        hass.pool.worker_count = 2
        self.assertTrue(setup_component(hass, logentries.DOMAIN, config))
        self.assertTrue(hass.bus.listen.called)
        self.assertEqual(EVENT_STATE_CHANGED,
                         hass.bus.listen.call_args_list[0][0][0])

    def test_setup_config_defaults(self):
        """Test setup with defaults."""
        config = {
            'logentries': {
                'token': 'token',
            }
        }
        hass = mock.MagicMock()
        hass.pool.worker_count = 2
        self.assertTrue(setup_component(hass, logentries.DOMAIN, config))
        self.assertTrue(hass.bus.listen.called)
        self.assertEqual(EVENT_STATE_CHANGED,
                         hass.bus.listen.call_args_list[0][0][0])

    def _setup(self, mock_requests):
        """Test the setup."""
        self.mock_post = mock_requests.post
        self.mock_request_exception = Exception
        mock_requests.exceptions.RequestException = self.mock_request_exception
        config = {
            'logentries': {
                'token': 'token'
            }
        }
        self.hass = mock.MagicMock()
        self.hass.pool.worker_count = 2
        setup_component(self.hass, logentries.DOMAIN, config)
        self.handler_method = self.hass.bus.listen.call_args_list[0][0][1]

    @mock.patch.object(logentries, 'requests')
    @mock.patch('json.dumps')
    def test_event_listener(self, mock_dump, mock_requests):
        """Test event listener."""
        mock_dump.side_effect = lambda x: x
        self._setup(mock_requests)

        valid = {'1': 1,
                 '1.0': 1.0,
                 STATE_ON: 1,
                 STATE_OFF: 0,
                 'foo': 'foo'}
        for in_, out in valid.items():
            state = mock.MagicMock(state=in_,
                                   domain='fake',
                                   object_id='entity',
                                   attributes={})
            event = mock.MagicMock(data={'new_state': state},
                                   time_fired=12345)
            body = [{
                'domain': 'fake',
                'entity_id': 'entity',
                'attributes': {},
                'time': '12345',
                'value': out,
            }]
            payload = {'host': 'https://webhook.logentries.com/noformat/'
                       'logs/token',
                       'event': body}
            self.handler_method(event)
            self.mock_post.assert_called_once_with(
                payload['host'], data=payload, timeout=10)
            self.mock_post.reset_mock()
