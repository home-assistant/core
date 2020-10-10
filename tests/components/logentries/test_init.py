"""The tests for the Logentries component."""

import unittest
from unittest import mock

import homeassistant.components.logentries as logentries
from homeassistant.const import EVENT_STATE_CHANGED, STATE_OFF, STATE_ON
from homeassistant.setup import setup_component

from tests.common import get_test_home_assistant


class TestLogentries(unittest.TestCase):
    """Test the Logentries component."""

    def setUp(self):  # pylint: disable=invalid-name
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.addCleanup(self.tear_down_cleanup)

    def tear_down_cleanup(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup_config_full(self):
        """Test setup with all data."""
        config = {"logentries": {"token": "secret"}}
        self.hass.bus.listen = mock.MagicMock()
        assert setup_component(self.hass, logentries.DOMAIN, config)
        assert self.hass.bus.listen.called
        assert EVENT_STATE_CHANGED == self.hass.bus.listen.call_args_list[0][0][0]

    def test_setup_config_defaults(self):
        """Test setup with defaults."""
        config = {"logentries": {"token": "token"}}
        self.hass.bus.listen = mock.MagicMock()
        assert setup_component(self.hass, logentries.DOMAIN, config)
        assert self.hass.bus.listen.called
        assert EVENT_STATE_CHANGED == self.hass.bus.listen.call_args_list[0][0][0]

    def _setup(self, mock_requests):
        """Test the setup."""
        self.mock_post = mock_requests.post
        self.mock_request_exception = Exception
        mock_requests.exceptions.RequestException = self.mock_request_exception
        config = {"logentries": {"token": "token"}}
        self.hass.bus.listen = mock.MagicMock()
        setup_component(self.hass, logentries.DOMAIN, config)
        self.handler_method = self.hass.bus.listen.call_args_list[0][0][1]

    @mock.patch.object(logentries, "requests")
    @mock.patch("json.dumps")
    def test_event_listener(self, mock_dump, mock_requests):
        """Test event listener."""
        mock_dump.side_effect = lambda x: x
        self._setup(mock_requests)

        valid = {"1": 1, "1.0": 1.0, STATE_ON: 1, STATE_OFF: 0, "foo": "foo"}
        for in_, out in valid.items():
            state = mock.MagicMock(
                state=in_, domain="fake", object_id="entity", attributes={}
            )
            event = mock.MagicMock(data={"new_state": state}, time_fired=12345)
            body = [
                {
                    "domain": "fake",
                    "entity_id": "entity",
                    "attributes": {},
                    "time": "12345",
                    "value": out,
                }
            ]
            payload = {
                "host": "https://webhook.logentries.com/noformat/logs/token",
                "event": body,
            }
            self.handler_method(event)
            assert self.mock_post.call_count == 1
            assert self.mock_post.call_args == mock.call(
                payload["host"], data=payload, timeout=10
            )
            self.mock_post.reset_mock()
