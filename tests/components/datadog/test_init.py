"""The tests for the Datadog component."""
import unittest
from unittest import mock

import homeassistant.components.datadog as datadog
from homeassistant.const import (
    EVENT_LOGBOOK_ENTRY,
    EVENT_STATE_CHANGED,
    STATE_OFF,
    STATE_ON,
)
import homeassistant.core as ha
from homeassistant.setup import setup_component

from tests.common import assert_setup_component, get_test_home_assistant


class TestDatadog(unittest.TestCase):
    """Test the Datadog component."""

    def setUp(self):  # pylint: disable=invalid-name
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.addCleanup(self.tear_down_cleanup)

    def tear_down_cleanup(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_invalid_config(self):
        """Test invalid configuration."""
        with assert_setup_component(0):
            assert not setup_component(
                self.hass, datadog.DOMAIN, {datadog.DOMAIN: {"host1": "host1"}}
            )

    @mock.patch("homeassistant.components.datadog.statsd")
    @mock.patch("homeassistant.components.datadog.initialize")
    def test_datadog_setup_full(self, mock_connection, mock_client):
        """Test setup with all data."""
        self.hass.bus.listen = mock.MagicMock()

        assert setup_component(
            self.hass,
            datadog.DOMAIN,
            {datadog.DOMAIN: {"host": "host", "port": 123, "rate": 1, "prefix": "foo"}},
        )

        assert mock_connection.call_count == 1
        assert mock_connection.call_args == mock.call(
            statsd_host="host", statsd_port=123
        )

        assert self.hass.bus.listen.called
        assert EVENT_LOGBOOK_ENTRY == self.hass.bus.listen.call_args_list[0][0][0]
        assert EVENT_STATE_CHANGED == self.hass.bus.listen.call_args_list[1][0][0]

    @mock.patch("homeassistant.components.datadog.statsd")
    @mock.patch("homeassistant.components.datadog.initialize")
    def test_datadog_setup_defaults(self, mock_connection, mock_client):
        """Test setup with defaults."""
        self.hass.bus.listen = mock.MagicMock()

        assert setup_component(
            self.hass,
            datadog.DOMAIN,
            {
                datadog.DOMAIN: {
                    "host": "host",
                    "port": datadog.DEFAULT_PORT,
                    "prefix": datadog.DEFAULT_PREFIX,
                }
            },
        )

        assert mock_connection.call_count == 1
        assert mock_connection.call_args == mock.call(
            statsd_host="host", statsd_port=8125
        )
        assert self.hass.bus.listen.called

    @mock.patch("homeassistant.components.datadog.statsd")
    @mock.patch("homeassistant.components.datadog.initialize")
    def test_logbook_entry(self, mock_connection, mock_client):
        """Test event listener."""
        self.hass.bus.listen = mock.MagicMock()

        assert setup_component(
            self.hass,
            datadog.DOMAIN,
            {datadog.DOMAIN: {"host": "host", "rate": datadog.DEFAULT_RATE}},
        )

        assert self.hass.bus.listen.called
        handler_method = self.hass.bus.listen.call_args_list[0][0][1]

        event = {
            "domain": "automation",
            "entity_id": "sensor.foo.bar",
            "message": "foo bar biz",
            "name": "triggered something",
        }
        handler_method(mock.MagicMock(data=event))

        assert mock_client.event.call_count == 1
        assert mock_client.event.call_args == mock.call(
            title="Home Assistant",
            text="%%% \n **{}** {} \n %%%".format(event["name"], event["message"]),
            tags=["entity:sensor.foo.bar", "domain:automation"],
        )

        mock_client.event.reset_mock()

    @mock.patch("homeassistant.components.datadog.statsd")
    @mock.patch("homeassistant.components.datadog.initialize")
    def test_state_changed(self, mock_connection, mock_client):
        """Test event listener."""
        self.hass.bus.listen = mock.MagicMock()

        assert setup_component(
            self.hass,
            datadog.DOMAIN,
            {
                datadog.DOMAIN: {
                    "host": "host",
                    "prefix": "ha",
                    "rate": datadog.DEFAULT_RATE,
                }
            },
        )

        assert self.hass.bus.listen.called
        handler_method = self.hass.bus.listen.call_args_list[1][0][1]

        valid = {"1": 1, "1.0": 1.0, STATE_ON: 1, STATE_OFF: 0}

        attributes = {"elevation": 3.2, "temperature": 5.0, "up": True, "down": False}

        for in_, out in valid.items():
            state = mock.MagicMock(
                domain="sensor",
                entity_id="sensor.foo.bar",
                state=in_,
                attributes=attributes,
            )
            handler_method(mock.MagicMock(data={"new_state": state}))

            assert mock_client.gauge.call_count == 5

            for attribute, value in attributes.items():
                value = int(value) if isinstance(value, bool) else value
                mock_client.gauge.assert_has_calls(
                    [
                        mock.call(
                            f"ha.sensor.{attribute}",
                            value,
                            sample_rate=1,
                            tags=[f"entity:{state.entity_id}"],
                        )
                    ]
                )

            assert mock_client.gauge.call_args == mock.call(
                "ha.sensor", out, sample_rate=1, tags=[f"entity:{state.entity_id}"],
            )

            mock_client.gauge.reset_mock()

        for invalid in ("foo", "", object):
            handler_method(
                mock.MagicMock(data={"new_state": ha.State("domain.test", invalid, {})})
            )
            assert not mock_client.gauge.called
