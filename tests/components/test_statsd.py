"""The tests for the StatsD feeder."""
import unittest
from unittest import mock

import voluptuous as vol

from homeassistant.setup import setup_component
import homeassistant.core as ha
import homeassistant.components.statsd as statsd
from homeassistant.const import (STATE_ON, STATE_OFF, EVENT_STATE_CHANGED)

from tests.common import get_test_home_assistant


class TestStatsd(unittest.TestCase):
    """Test the StatsD component."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def test_invalid_config(self):
        """Test configuration with defaults."""
        config = {
            'statsd': {
                'host1': 'host1',
            }
        }

        with self.assertRaises(vol.Invalid):
            statsd.CONFIG_SCHEMA(None)
        with self.assertRaises(vol.Invalid):
            statsd.CONFIG_SCHEMA(config)

    @mock.patch('statsd.StatsClient')
    def test_statsd_setup_full(self, mock_connection):
        """Test setup with all data."""
        config = {
            'statsd': {
                'host': 'host',
                'port': 123,
                'rate': 1,
                'prefix': 'foo',
            }
        }
        self.hass.bus.listen = mock.MagicMock()
        self.assertTrue(setup_component(self.hass, statsd.DOMAIN, config))
        self.assertEqual(mock_connection.call_count, 1)
        self.assertEqual(
            mock_connection.call_args,
            mock.call(host='host', port=123, prefix='foo')
        )

        self.assertTrue(self.hass.bus.listen.called)
        self.assertEqual(EVENT_STATE_CHANGED,
                         self.hass.bus.listen.call_args_list[0][0][0])

    @mock.patch('statsd.StatsClient')
    def test_statsd_setup_defaults(self, mock_connection):
        """Test setup with defaults."""
        config = {
            'statsd': {
                'host': 'host',
            }
        }

        config['statsd'][statsd.CONF_PORT] = statsd.DEFAULT_PORT
        config['statsd'][statsd.CONF_PREFIX] = statsd.DEFAULT_PREFIX

        self.hass.bus.listen = mock.MagicMock()
        self.assertTrue(setup_component(self.hass, statsd.DOMAIN, config))
        self.assertEqual(mock_connection.call_count, 1)
        self.assertEqual(
            mock_connection.call_args,
            mock.call(host='host', port=8125, prefix='hass')
        )
        self.assertTrue(self.hass.bus.listen.called)

    @mock.patch('statsd.StatsClient')
    def test_event_listener_defaults(self, mock_client):
        """Test event listener."""
        config = {
            'statsd': {
                'host': 'host',
            }
        }

        config['statsd'][statsd.CONF_RATE] = statsd.DEFAULT_RATE

        self.hass.bus.listen = mock.MagicMock()
        setup_component(self.hass, statsd.DOMAIN, config)
        self.assertTrue(self.hass.bus.listen.called)
        handler_method = self.hass.bus.listen.call_args_list[0][0][1]

        valid = {'1': 1,
                 '1.0': 1.0,
                 STATE_ON: 1,
                 STATE_OFF: 0}
        for in_, out in valid.items():
            state = mock.MagicMock(state=in_,
                                   attributes={"attribute key": 3.2})
            handler_method(mock.MagicMock(data={'new_state': state}))
            mock_client.return_value.gauge.assert_has_calls([
                mock.call(state.entity_id, out, statsd.DEFAULT_RATE),
            ])

            mock_client.return_value.gauge.reset_mock()

            self.assertEqual(mock_client.return_value.incr.call_count, 1)
            self.assertEqual(
                mock_client.return_value.incr.call_args,
                mock.call(state.entity_id, rate=statsd.DEFAULT_RATE)
            )
            mock_client.return_value.incr.reset_mock()

        for invalid in ('foo', '', object):
            handler_method(mock.MagicMock(data={
                'new_state': ha.State('domain.test', invalid, {})}))
            self.assertFalse(mock_client.return_value.gauge.called)
            self.assertTrue(mock_client.return_value.incr.called)

    @mock.patch('statsd.StatsClient')
    def test_event_listener_attr_details(self, mock_client):
        """Test event listener."""
        config = {
            'statsd': {
                'host': 'host',
                'log_attributes': True
            }
        }

        config['statsd'][statsd.CONF_RATE] = statsd.DEFAULT_RATE

        self.hass.bus.listen = mock.MagicMock()
        setup_component(self.hass, statsd.DOMAIN, config)
        self.assertTrue(self.hass.bus.listen.called)
        handler_method = self.hass.bus.listen.call_args_list[0][0][1]

        valid = {'1': 1,
                 '1.0': 1.0,
                 STATE_ON: 1,
                 STATE_OFF: 0}
        for in_, out in valid.items():
            state = mock.MagicMock(state=in_,
                                   attributes={"attribute key": 3.2})
            handler_method(mock.MagicMock(data={'new_state': state}))
            mock_client.return_value.gauge.assert_has_calls([
                mock.call("%s.state" % state.entity_id,
                          out, statsd.DEFAULT_RATE),
                mock.call("%s.attribute_key" % state.entity_id,
                          3.2, statsd.DEFAULT_RATE),
            ])

            mock_client.return_value.gauge.reset_mock()

            self.assertEqual(mock_client.return_value.incr.call_count, 1)
            self.assertEqual(
                mock_client.return_value.incr.call_args,
                mock.call(state.entity_id, rate=statsd.DEFAULT_RATE)
            )
            mock_client.return_value.incr.reset_mock()

        for invalid in ('foo', '', object):
            handler_method(mock.MagicMock(data={
                'new_state': ha.State('domain.test', invalid, {})}))
            self.assertFalse(mock_client.return_value.gauge.called)
            self.assertTrue(mock_client.return_value.incr.called)
