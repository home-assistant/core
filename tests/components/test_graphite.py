"""The tests for the Graphite component."""
import socket
import unittest
from unittest import mock
from unittest.mock import patch

from homeassistant.bootstrap import setup_component
import homeassistant.core as ha
import homeassistant.components.graphite as graphite
from homeassistant.const import (
    EVENT_STATE_CHANGED, EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP,
    STATE_ON, STATE_OFF)
from tests.common import get_test_home_assistant


class TestGraphite(unittest.TestCase):
    """Test the Graphite component."""

    def setup_method(self, method):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.gf = graphite.GraphiteFeeder(self.hass, 'foo', 123, 'ha')

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    @patch('socket.socket')
    def test_setup(self, mock_socket):
        """Test setup."""
        assert setup_component(self.hass, graphite.DOMAIN, {'graphite': {}})
        mock_socket.assert_called_once_with(socket.AF_INET, socket.SOCK_STREAM)

    @patch('socket.socket')
    @patch('homeassistant.components.graphite.GraphiteFeeder')
    def test_full_config(self, mock_gf, mock_socket):
        """Test setup with full configuration."""
        config = {
            'graphite': {
                'host': 'foo',
                'port': 123,
                'prefix': 'me',
            }
        }

        self.assertTrue(setup_component(self.hass, graphite.DOMAIN, config))
        mock_gf.assert_called_once_with(self.hass, 'foo', 123, 'me')
        mock_socket.assert_called_once_with(socket.AF_INET, socket.SOCK_STREAM)

    @patch('socket.socket')
    @patch('homeassistant.components.graphite.GraphiteFeeder')
    def test_config_port(self, mock_gf, mock_socket):
        """Test setup with invalid port."""
        config = {
            'graphite': {
                'host': 'foo',
                'port': 2003,
            }
        }

        self.assertTrue(setup_component(self.hass, graphite.DOMAIN, config))
        self.assertTrue(mock_gf.called)
        mock_socket.assert_called_once_with(socket.AF_INET, socket.SOCK_STREAM)

    def test_subscribe(self):
        """Test the subscription."""
        fake_hass = mock.MagicMock()
        gf = graphite.GraphiteFeeder(fake_hass, 'foo', 123, 'ha')
        fake_hass.bus.listen_once.has_calls([
            mock.call(EVENT_HOMEASSISTANT_START, gf.start_listen),
            mock.call(EVENT_HOMEASSISTANT_STOP, gf.shutdown),
        ])
        fake_hass.bus.listen.assert_called_once_with(
            EVENT_STATE_CHANGED, gf.event_listener)

    def test_start(self):
        """Test the start."""
        with mock.patch.object(self.gf, 'start') as mock_start:
            self.gf.start_listen('event')
            mock_start.assert_called_once_with()

    def test_shutdown(self):
        """Test the shutdown."""
        with mock.patch.object(self.gf, '_queue') as mock_queue:
            self.gf.shutdown('event')
            mock_queue.put.assert_called_once_with(self.gf._quit_object)

    def test_event_listener(self):
        """Test the event listener."""
        with mock.patch.object(self.gf, '_queue') as mock_queue:
            self.gf.event_listener('foo')
            mock_queue.put.assert_called_once_with('foo')

    @patch('time.time')
    def test_report_attributes(self, mock_time):
        """Test the reporting with attributes."""
        mock_time.return_value = 12345
        attrs = {'foo': 1,
                 'bar': 2.0,
                 'baz': True,
                 'bat': 'NaN',
                 }

        expected = [
            'ha.entity.state 0.000000 12345',
            'ha.entity.foo 1.000000 12345',
            'ha.entity.bar 2.000000 12345',
            'ha.entity.baz 1.000000 12345',
            ]

        state = mock.MagicMock(state=0, attributes=attrs)
        with mock.patch.object(self.gf, '_send_to_graphite') as mock_send:
            self.gf._report_attributes('entity', state)
            actual = mock_send.call_args_list[0][0][0].split('\n')
            self.assertEqual(sorted(expected), sorted(actual))

    @patch('time.time')
    def test_report_with_string_state(self, mock_time):
        """Test the reporting with strings."""
        mock_time.return_value = 12345
        expected = [
            'ha.entity.foo 1.000000 12345',
            'ha.entity.state 1.000000 12345',
            ]

        state = mock.MagicMock(state='above_horizon', attributes={'foo': 1.0})
        with mock.patch.object(self.gf, '_send_to_graphite') as mock_send:
            self.gf._report_attributes('entity', state)
            actual = mock_send.call_args_list[0][0][0].split('\n')
            self.assertEqual(sorted(expected), sorted(actual))

    @patch('time.time')
    def test_report_with_binary_state(self, mock_time):
        """Test the reporting with binary state."""
        mock_time.return_value = 12345
        state = ha.State('domain.entity', STATE_ON, {'foo': 1.0})
        with mock.patch.object(self.gf, '_send_to_graphite') as mock_send:
            self.gf._report_attributes('entity', state)
            expected = ['ha.entity.foo 1.000000 12345',
                        'ha.entity.state 1.000000 12345']
            actual = mock_send.call_args_list[0][0][0].split('\n')
            self.assertEqual(sorted(expected), sorted(actual))

        state.state = STATE_OFF
        with mock.patch.object(self.gf, '_send_to_graphite') as mock_send:
            self.gf._report_attributes('entity', state)
            expected = ['ha.entity.foo 1.000000 12345',
                        'ha.entity.state 0.000000 12345']
            actual = mock_send.call_args_list[0][0][0].split('\n')
            self.assertEqual(sorted(expected), sorted(actual))

    @patch('time.time')
    def test_send_to_graphite_errors(self, mock_time):
        """Test the sending with errors."""
        mock_time.return_value = 12345
        state = ha.State('domain.entity', STATE_ON, {'foo': 1.0})
        with mock.patch.object(self.gf, '_send_to_graphite') as mock_send:
            mock_send.side_effect = socket.error
            self.gf._report_attributes('entity', state)
            mock_send.side_effect = socket.gaierror
            self.gf._report_attributes('entity', state)

    @patch('socket.socket')
    def test_send_to_graphite(self, mock_socket):
        """Test the sending of data."""
        self.gf._send_to_graphite('foo')
        mock_socket.assert_called_once_with(socket.AF_INET,
                                            socket.SOCK_STREAM)
        sock = mock_socket.return_value
        sock.connect.assert_called_once_with(('foo', 123))
        sock.sendall.assert_called_once_with('foo'.encode('ascii'))
        sock.send.assert_called_once_with('\n'.encode('ascii'))
        sock.close.assert_called_once_with()

    def test_run_stops(self):
        """Test the stops."""
        with mock.patch.object(self.gf, '_queue') as mock_queue:
            mock_queue.get.return_value = self.gf._quit_object
            self.assertEqual(None, self.gf.run())
            mock_queue.get.assert_called_once_with()
            mock_queue.task_done.assert_called_once_with()

    def test_run(self):
        """Test the running."""
        runs = []
        event = mock.MagicMock(event_type=EVENT_STATE_CHANGED,
                               data={'entity_id': 'entity',
                                     'new_state': mock.MagicMock()})

        def fake_get():
            if len(runs) >= 2:
                return self.gf._quit_object
            elif runs:
                runs.append(1)
                return mock.MagicMock(event_type='somethingelse',
                                      data={'new_event': None})
            else:
                runs.append(1)
                return event

        with mock.patch.object(self.gf, '_queue') as mock_queue:
            with mock.patch.object(self.gf, '_report_attributes') as mock_r:
                mock_queue.get.side_effect = fake_get
                self.gf.run()
                # Twice for two events, once for the stop
                self.assertEqual(3, mock_queue.task_done.call_count)
                mock_r.assert_called_once_with(
                    'entity',
                    event.data['new_state'])
