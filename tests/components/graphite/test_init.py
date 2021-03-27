"""The tests for the Graphite component."""
import socket
import unittest
from unittest import mock
from unittest.mock import patch

import homeassistant.components.graphite as graphite
from homeassistant.const import (
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
    EVENT_STATE_CHANGED,
    STATE_OFF,
    STATE_ON,
)
import homeassistant.core as ha
from homeassistant.setup import setup_component

from tests.common import get_test_home_assistant


class TestGraphite(unittest.TestCase):
    """Test the Graphite component."""

    def setup_method(self, method):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.gf = graphite.GraphiteFeeder(self.hass, "foo", 123, "tcp", "ha")

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    @patch("socket.socket")
    def test_setup(self, mock_socket):
        """Test setup."""
        assert setup_component(self.hass, graphite.DOMAIN, {"graphite": {}})
        assert mock_socket.call_count == 1
        assert mock_socket.call_args == mock.call(socket.AF_INET, socket.SOCK_STREAM)

    @patch("socket.socket")
    @patch("homeassistant.components.graphite.GraphiteFeeder")
    def test_full_config(self, mock_gf, mock_socket):
        """Test setup with full configuration."""
        config = {"graphite": {"host": "foo", "port": 123, "prefix": "me"}}

        assert setup_component(self.hass, graphite.DOMAIN, config)
        assert mock_gf.call_count == 1
        assert mock_gf.call_args == mock.call(self.hass, "foo", 123, "tcp", "me")
        assert mock_socket.call_count == 1
        assert mock_socket.call_args == mock.call(socket.AF_INET, socket.SOCK_STREAM)

    @patch("socket.socket")
    @patch("homeassistant.components.graphite.GraphiteFeeder")
    def test_full_udp_config(self, mock_gf, mock_socket):
        """Test setup with full configuration and UDP protocol."""
        config = {
            "graphite": {"host": "foo", "port": 123, "protocol": "udp", "prefix": "me"}
        }

        assert setup_component(self.hass, graphite.DOMAIN, config)
        assert mock_gf.call_count == 1
        assert mock_gf.call_args == mock.call(self.hass, "foo", 123, "udp", "me")
        assert mock_socket.call_count == 0

    @patch("socket.socket")
    @patch("homeassistant.components.graphite.GraphiteFeeder")
    def test_config_port(self, mock_gf, mock_socket):
        """Test setup with invalid port."""
        config = {"graphite": {"host": "foo", "port": 2003}}

        assert setup_component(self.hass, graphite.DOMAIN, config)
        assert mock_gf.called
        assert mock_socket.call_count == 1
        assert mock_socket.call_args == mock.call(socket.AF_INET, socket.SOCK_STREAM)

    def test_subscribe(self):
        """Test the subscription."""
        fake_hass = mock.MagicMock()
        gf = graphite.GraphiteFeeder(fake_hass, "foo", 123, "tcp", "ha")
        fake_hass.bus.listen_once.has_calls(
            [
                mock.call(EVENT_HOMEASSISTANT_START, gf.start_listen),
                mock.call(EVENT_HOMEASSISTANT_STOP, gf.shutdown),
            ]
        )
        assert fake_hass.bus.listen.call_count == 1
        assert fake_hass.bus.listen.call_args == mock.call(
            EVENT_STATE_CHANGED, gf.event_listener
        )

    def test_start(self):
        """Test the start."""
        with mock.patch.object(self.gf, "start") as mock_start:
            self.gf.start_listen("event")
            assert mock_start.call_count == 1
            assert mock_start.call_args == mock.call()

    def test_shutdown(self):
        """Test the shutdown."""
        with mock.patch.object(self.gf, "_queue") as mock_queue:
            self.gf.shutdown("event")
            assert mock_queue.put.call_count == 1
            assert mock_queue.put.call_args == mock.call(self.gf._quit_object)

    def test_event_listener(self):
        """Test the event listener."""
        with mock.patch.object(self.gf, "_queue") as mock_queue:
            self.gf.event_listener("foo")
            assert mock_queue.put.call_count == 1
            assert mock_queue.put.call_args == mock.call("foo")

    @patch("time.time")
    def test_report_attributes(self, mock_time):
        """Test the reporting with attributes."""
        mock_time.return_value = 12345
        attrs = {"foo": 1, "bar": 2.0, "baz": True, "bat": "NaN"}

        expected = [
            "ha.entity.state 0.000000 12345",
            "ha.entity.foo 1.000000 12345",
            "ha.entity.bar 2.000000 12345",
            "ha.entity.baz 1.000000 12345",
        ]

        state = mock.MagicMock(state=0, attributes=attrs)
        with mock.patch.object(self.gf, "_send_to_graphite") as mock_send:
            self.gf._report_attributes("entity", state)
            actual = mock_send.call_args_list[0][0][0].split("\n")
            assert sorted(expected) == sorted(actual)

    @patch("time.time")
    def test_report_with_string_state(self, mock_time):
        """Test the reporting with strings."""
        mock_time.return_value = 12345
        expected = ["ha.entity.foo 1.000000 12345", "ha.entity.state 1.000000 12345"]

        state = mock.MagicMock(state="above_horizon", attributes={"foo": 1.0})
        with mock.patch.object(self.gf, "_send_to_graphite") as mock_send:
            self.gf._report_attributes("entity", state)
            actual = mock_send.call_args_list[0][0][0].split("\n")
            assert sorted(expected) == sorted(actual)

    @patch("time.time")
    def test_report_with_binary_state(self, mock_time):
        """Test the reporting with binary state."""
        mock_time.return_value = 12345
        state = ha.State("domain.entity", STATE_ON, {"foo": 1.0})
        with mock.patch.object(self.gf, "_send_to_graphite") as mock_send:
            self.gf._report_attributes("entity", state)
            expected = [
                "ha.entity.foo 1.000000 12345",
                "ha.entity.state 1.000000 12345",
            ]
            actual = mock_send.call_args_list[0][0][0].split("\n")
            assert sorted(expected) == sorted(actual)

        state.state = STATE_OFF
        with mock.patch.object(self.gf, "_send_to_graphite") as mock_send:
            self.gf._report_attributes("entity", state)
            expected = [
                "ha.entity.foo 1.000000 12345",
                "ha.entity.state 0.000000 12345",
            ]
            actual = mock_send.call_args_list[0][0][0].split("\n")
            assert sorted(expected) == sorted(actual)

    @patch("time.time")
    def test_send_to_graphite_errors(self, mock_time):
        """Test the sending with errors."""
        mock_time.return_value = 12345
        state = ha.State("domain.entity", STATE_ON, {"foo": 1.0})
        with mock.patch.object(self.gf, "_send_to_graphite") as mock_send:
            mock_send.side_effect = socket.error
            self.gf._report_attributes("entity", state)
            mock_send.side_effect = socket.gaierror
            self.gf._report_attributes("entity", state)

    @patch("socket.socket")
    def test_send_to_graphite(self, mock_socket):
        """Test the sending of data."""
        self.gf._send_to_graphite("foo")
        assert mock_socket.call_count == 1
        assert mock_socket.call_args == mock.call(socket.AF_INET, socket.SOCK_STREAM)
        sock = mock_socket.return_value
        assert sock.connect.call_count == 1
        assert sock.connect.call_args == mock.call(("foo", 123))
        assert sock.sendall.call_count == 1
        assert sock.sendall.call_args == mock.call(b"foo")
        assert sock.send.call_count == 1
        assert sock.send.call_args == mock.call(b"\n")
        assert sock.close.call_count == 1
        assert sock.close.call_args == mock.call()

    def test_run_stops(self):
        """Test the stops."""
        with mock.patch.object(self.gf, "_queue") as mock_queue:
            mock_queue.get.return_value = self.gf._quit_object
            assert self.gf.run() is None
            assert mock_queue.get.call_count == 1
            assert mock_queue.get.call_args == mock.call()
            assert mock_queue.task_done.call_count == 1
            assert mock_queue.task_done.call_args == mock.call()

    def test_run(self):
        """Test the running."""
        runs = []
        event = mock.MagicMock(
            event_type=EVENT_STATE_CHANGED,
            data={"entity_id": "entity", "new_state": mock.MagicMock()},
        )

        def fake_get():
            if len(runs) >= 2:
                return self.gf._quit_object
            if runs:
                runs.append(1)
                return mock.MagicMock(
                    event_type="somethingelse", data={"new_event": None}
                )
            runs.append(1)
            return event

        with mock.patch.object(self.gf, "_queue") as mock_queue, mock.patch.object(
            self.gf, "_report_attributes"
        ) as mock_r:
            mock_queue.get.side_effect = fake_get
            self.gf.run()
            # Twice for two events, once for the stop
            assert mock_queue.task_done.call_count == 3
            assert mock_r.call_count == 1
            assert mock_r.call_args == mock.call("entity", event.data["new_state"])
