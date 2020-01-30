"""The tests for the Splunk component."""
import json
import unittest
from unittest import mock

import homeassistant.components.splunk as splunk
from homeassistant.const import EVENT_STATE_CHANGED, STATE_OFF, STATE_ON
from homeassistant.core import State
from homeassistant.helpers import state as state_helper
from homeassistant.setup import setup_component
import homeassistant.util.dt as dt_util

from tests.common import get_test_home_assistant, mock_state_change_event


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
            "splunk": {
                "host": "host",
                "port": 123,
                "token": "secret",
                "ssl": "False",
                "verify_ssl": "True",
                "name": "hostname",
                "filter": {
                    "exclude_domains": ["fake"],
                    "exclude_entities": ["fake.entity"],
                },
            }
        }

        self.hass.bus.listen = mock.MagicMock()
        assert setup_component(self.hass, splunk.DOMAIN, config)
        assert self.hass.bus.listen.called
        assert EVENT_STATE_CHANGED == self.hass.bus.listen.call_args_list[0][0][0]

    def test_setup_config_defaults(self):
        """Test setup with defaults."""
        config = {"splunk": {"host": "host", "token": "secret"}}

        self.hass.bus.listen = mock.MagicMock()
        assert setup_component(self.hass, splunk.DOMAIN, config)
        assert self.hass.bus.listen.called
        assert EVENT_STATE_CHANGED == self.hass.bus.listen.call_args_list[0][0][0]

    def _setup(self, mock_requests):
        """Test the setup."""
        self.mock_post = mock_requests.post
        self.mock_request_exception = Exception
        mock_requests.exceptions.RequestException = self.mock_request_exception
        config = {"splunk": {"host": "host", "token": "secret", "port": 8088}}

        self.hass.bus.listen = mock.MagicMock()
        setup_component(self.hass, splunk.DOMAIN, config)
        self.handler_method = self.hass.bus.listen.call_args_list[0][0][1]

    @mock.patch.object(splunk, "requests")
    def test_event_listener(self, mock_requests):
        """Test event listener."""
        self._setup(mock_requests)

        now = dt_util.now()
        valid = {"1": 1, "1.0": 1.0, STATE_ON: 1, STATE_OFF: 0, "foo": "foo"}

        for in_, out in valid.items():
            state = mock.MagicMock(
                state=in_,
                domain="fake",
                object_id="entity",
                attributes={"datetime_attr": now},
            )
            event = mock.MagicMock(data={"new_state": state}, time_fired=12345)

            try:
                out = state_helper.state_as_number(state)
            except ValueError:
                out = state.state

            body = [
                {
                    "domain": "fake",
                    "entity_id": "entity",
                    "attributes": {"datetime_attr": now.isoformat()},
                    "time": "12345",
                    "value": out,
                    "host": "HASS",
                }
            ]

            payload = {
                "host": "http://host:8088/services/collector/event",
                "event": body,
            }
            self.handler_method(event)
            assert self.mock_post.call_count == 1
            assert self.mock_post.call_args == mock.call(
                payload["host"],
                data=json.dumps(payload),
                headers={"Authorization": "Splunk secret"},
                timeout=10,
                verify=True,
            )
            self.mock_post.reset_mock()

    def _setup_with_filter(self):
        """Test the setup."""
        config = {
            "splunk": {
                "host": "host",
                "token": "secret",
                "port": 8088,
                "filter": {
                    "exclude_domains": ["excluded_domain"],
                    "exclude_entities": ["other_domain.excluded_entity"],
                },
            }
        }

        setup_component(self.hass, splunk.DOMAIN, config)

    @mock.patch.object(splunk, "post_request")
    def test_splunk_entityfilter(self, mock_requests):
        """Test event listener."""
        self._setup_with_filter()

        testdata = [
            {"entity_id": "other_domain.other_entity", "filter_expected": False},
            {"entity_id": "other_domain.excluded_entity", "filter_expected": True},
            {"entity_id": "excluded_domain.other_entity", "filter_expected": True},
        ]

        for test in testdata:
            mock_state_change_event(self.hass, State(test["entity_id"], "on"))
            self.hass.block_till_done()

            if test["filter_expected"]:
                assert not splunk.post_request.called
            else:
                assert splunk.post_request.called

            splunk.post_request.reset_mock()
