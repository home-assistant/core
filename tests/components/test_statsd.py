"""The tests for the StatsD feeder."""
import unittest
from unittest import mock

import homeassistant.core as ha
import homeassistant.components.statsd as statsd
from homeassistant.const import STATE_ON, STATE_OFF, EVENT_STATE_CHANGED


class TestStatsd(unittest.TestCase):
    """Test the StatsD component."""

    @mock.patch('statsd.Connection')
    @mock.patch('statsd.Gauge')
    def test_statsd_setup_full(self, mock_gauge, mock_connection):
        """Test setup with all data."""
        config = {
            'statsd': {
                'host': 'host',
                'port': 123,
                'sample_rate': 1,
                'prefix': 'foo',
            }
        }
        hass = mock.MagicMock()
        self.assertTrue(statsd.setup(hass, config))
        mock_connection.assert_called_once_with(host='host', port=123,
                                                sample_rate=1,
                                                disabled=False)
        mock_gauge.assert_called_once_with('foo',
                                           mock_connection.return_value)
        self.assertTrue(hass.bus.listen.called)
        self.assertEqual(EVENT_STATE_CHANGED,
                         hass.bus.listen.call_args_list[0][0][0])

    @mock.patch('statsd.Connection')
    @mock.patch('statsd.Gauge')
    def test_statsd_setup_defaults(self, mock_gauge, mock_connection):
        """Test setup with defaults."""
        config = {
            'statsd': {
                'host': 'host',
            }
        }
        hass = mock.MagicMock()
        self.assertTrue(statsd.setup(hass, config))
        mock_connection.assert_called_once_with(
            host='host',
            port=statsd.DEFAULT_PORT,
            sample_rate=statsd.DEFAULT_RATE,
            disabled=False)
        mock_gauge.assert_called_once_with(statsd.DEFAULT_PREFIX,
                                           mock_connection.return_value)
        self.assertTrue(hass.bus.listen.called)

    @mock.patch('statsd.Connection')
    @mock.patch('statsd.Gauge')
    def test_event_listener(self, mock_gauge, mock_connection):
        """Test event listener."""
        config = {
            'statsd': {
                'host': 'host',
            }
        }
        hass = mock.MagicMock()
        statsd.setup(hass, config)
        self.assertTrue(hass.bus.listen.called)
        handler_method = hass.bus.listen.call_args_list[0][0][1]

        valid = {'1': 1,
                 '1.0': 1.0,
                 STATE_ON: 1,
                 STATE_OFF: 0}
        for in_, out in valid.items():
            state = mock.MagicMock(state=in_)
            handler_method(mock.MagicMock(data={'new_state': state}))
            mock_gauge.return_value.send.assert_called_once_with(
                state.entity_id, out)
            mock_gauge.return_value.send.reset_mock()

        for invalid in ('foo', '', object):
            handler_method(mock.MagicMock(data={
                'new_state': ha.State('domain.test', invalid, {})}))
            self.assertFalse(mock_gauge.return_value.send.called)
