"""The tests for the Splunk component."""
import json
import unittest
from unittest import mock

from homeassistant.setup import setup_component
import homeassistant.components.splunk as splunk
from homeassistant.const import STATE_ON, STATE_OFF, EVENT_STATE_CHANGED
from homeassistant.helpers import state as state_helper
import homeassistant.util.dt as dt_util

from tests.common import get_test_home_assistant


class TestSplunk(unittest.TestCase):
    """Test the Splunk component."""

    def setUp(self):  # pylint: disable=invalid-name
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup_config_full(self):
        """Test setup with all data."""
        config = {
            'splunk': {
                'host': 'host',
                'port': 123,
                'token': 'secret',
                'ssl': 'False',
                'verify_ssl': 'True',
                'name': 'hostname',
            }
        }

        self.hass.bus.listen = mock.MagicMock()
        assert setup_component(self.hass, splunk.DOMAIN, config)
        assert self.hass.bus.listen.called
        assert EVENT_STATE_CHANGED == \
            self.hass.bus.listen.call_args_list[0][0][0]

    def test_setup_config_defaults(self):
        """Test setup with defaults."""
        config = {
            'splunk': {
                'host': 'host',
                'token': 'secret',
            }
        }

        self.hass.bus.listen = mock.MagicMock()
        assert setup_component(self.hass, splunk.DOMAIN, config)
        assert self.hass.bus.listen.called
        assert EVENT_STATE_CHANGED == \
            self.hass.bus.listen.call_args_list[0][0][0]

    def _setup(self, mock_requests):
        """Test the setup."""
        self.mock_post = mock_requests.post
        self.mock_request_exception = Exception
        mock_requests.exceptions.RequestException = self.mock_request_exception
        config = {
            'splunk': {
                'host': 'host',
                'token': 'secret',
                'port': 8088,
            }
        }

        self.hass.bus.listen = mock.MagicMock()
        setup_component(self.hass, splunk.DOMAIN, config)
        self.handler_method = self.hass.bus.listen.call_args_list[0][0][1]

    @mock.patch.object(splunk, 'requests')
    def test_event_listener(self, mock_requests):
        """Test event listener."""
        self._setup(mock_requests)

        now = dt_util.now()
        valid = {
            '1': 1,
            '1.0': 1.0,
            STATE_ON: 1,
            STATE_OFF: 0,
            'foo': 'foo',
        }

        for in_, out in valid.items():
            state = mock.MagicMock(
                state=in_, domain='fake', object_id='entity',
                attributes={'datetime_attr': now})
            event = mock.MagicMock(data={'new_state': state}, time_fired=12345)

            try:
                out = state_helper.state_as_number(state)
            except ValueError:
                out = state.state

            body = [{
                'domain': 'fake',
                'entity_id': 'entity',
                'attributes': {
                    'datetime_attr': now.isoformat()
                },
                'time': '12345',
                'value': out,
                'host': 'HASS',
            }]

            payload = {'host': 'http://host:8088/services/collector/event',
                       'event': body}
            self.handler_method(event)
            assert self.mock_post.call_count == 1
            assert self.mock_post.call_args == \
                mock.call(
                    payload['host'], data=json.dumps(payload),
                    headers={'Authorization': 'Splunk secret'},
                    timeout=10, verify=True)
            self.mock_post.reset_mock()
